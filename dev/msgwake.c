/* Wake-up latency test: a worker thread hands work to the GUI thread the ways apps do
 * (posted message, event + MsgWait, thread message, timer) and we time how long the GUI
 * thread takes to notice. Results go to msgwake.log next to the exe.
 * Build: zig cc -target x86_64-windows-gnu -o msgwake.exe msgwake.c -luser32 */
#include <windows.h>
#include <stdio.h>

#define N 300
static FILE *out;
static HWND win;
static HANDLE evt, ready;
static volatile LONG mode;
static LARGE_INTEGER freq;
static LONGLONG sent;
static double lat[N];
static int count;

static double now_ms(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return t.QuadPart * 1000.0 / freq.QuadPart; }

static void record(void)
{
    double d = now_ms() - sent / 1000.0;
    if (count < N) lat[count++] = d;
}

static void report(const char *name)
{
    double sum = 0, max = 0; int i, slow = 0;
    for (i = 0; i < count; i++) { sum += lat[i]; if (lat[i] > max) max = lat[i]; if (lat[i] > 20) slow++; }
    fprintf(out, "%-34s n=%d avg=%.2fms max=%.2fms >20ms:%d\n", name, count, count ? sum / count : 0, max, slow);
    fflush(out);
    count = 0;
}

static DWORD WINAPI worker(void *arg)
{
    DWORD tid = (DWORD)(ULONG_PTR)arg;
    int i;
    for (i = 0; i < N; i++) {
        Sleep(2 + (i % 5));
        sent = (LONGLONG)(now_ms() * 1000);
        switch (mode) {
        case 0: case 2: PostMessageW(win, WM_APP, 0, 0); break;
        case 1: SetEvent(evt); break;
        case 3: PostThreadMessageW(tid, WM_APP + 1, 0, 0); break;
        }
        WaitForSingleObject(ready, 1000);
    }
    return 0;
}

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_APP) { record(); SetEvent(ready); return 0; }
    return DefWindowProcW(h, msg, wp, lp);
}

static void run(int m, const char *name)
{
    HANDLE th;
    MSG msg;
    mode = m;
    th = CreateThread(NULL, 0, worker, (void *)(ULONG_PTR)GetCurrentThreadId(), 0, NULL);
    while (WaitForSingleObject(th, 0) == WAIT_TIMEOUT) {
        DWORD r;
        if (m == 2) {   /* filtered peek first (timer range only), then a plain MsgWait */
            PeekMessageW(&msg, NULL, WM_TIMER, WM_TIMER, PM_NOREMOVE);
            r = MsgWaitForMultipleObjectsEx(0, NULL, 50, QS_ALLINPUT, 0);
        } else
            r = MsgWaitForMultipleObjectsEx(m == 1, &evt, 50, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
        if (m == 1 && r == WAIT_OBJECT_0) { record(); SetEvent(ready); }
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_APP + 1 && !msg.hwnd) { record(); SetEvent(ready); continue; }
            DispatchMessageW(&msg);
        }
    }
    CloseHandle(th);
    report(name);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, LPWSTR cmd, int show)
{
    WNDCLASSW wc = { 0, proc, 0, 0, inst, NULL, NULL, NULL, NULL, L"msgwake" };
    char path[MAX_PATH], *slash;
    double last, t, max = 0; int ticks = 0; MSG msg;
    GetModuleFileNameA(NULL, path, MAX_PATH);
    if ((slash = strrchr(path, '\\'))) strcpy(slash + 1, "msgwake.log");
    out = fopen(path, "w");
    QueryPerformanceFrequency(&freq);
    RegisterClassW(&wc);
    win = CreateWindowW(L"msgwake", L"msgwake", WS_OVERLAPPEDWINDOW | WS_VISIBLE, 0, 0, 200, 100, NULL, NULL, inst, NULL);
    evt = CreateEventW(NULL, FALSE, FALSE, NULL);
    ready = CreateEventW(NULL, FALSE, FALSE, NULL);
    run(0, "PostMessage -> MsgWait(INPUTAVAIL)");
    run(1, "SetEvent -> MsgWait(event)");
    run(2, "PostMessage after filtered Peek");
    run(3, "PostThreadMessage -> MsgWait");
    SetTimer(win, 1, 16, NULL);              /* 16 ms timer: interval jitter */
    last = now_ms();
    while (ticks < 120 && GetMessageW(&msg, NULL, 0, 0)) {
        if (msg.message == WM_TIMER) { t = now_ms(); if (t - last > max) max = t - last; last = t; ticks++; }
        DispatchMessageW(&msg);
    }
    fprintf(out, "%-34s n=%d max interval=%.2fms (expect ~16)\n", "SetTimer 16ms", ticks, max);
    fclose(out);
    return 0;
}
