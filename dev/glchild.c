/* OpenGL child-window present test (like After Effects' viewer): each frame clears a GL
 * child window to a new colour, swaps, then reads the pixel back from the screen. If the
 * screen shows the previous frame's colour, presentation lags one frame behind.
 * Results go to glchild.log next to the exe.
 * Build: zig cc -target x86_64-windows-gnu -o glchild.exe glchild.c -lopengl32 -lgdi32 -luser32 */
#include <windows.h>
#include <GL/gl.h>
#include <stdio.h>

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_DESTROY) PostQuitMessage(0);
    return DefWindowProcW(h, msg, wp, lp);
}

static void pump(void)
{
    MSG msg;
    while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) DispatchMessageW(&msg);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, LPWSTR cmd, int show)
{
    static const COLORREF colors[] = { RGB(255, 0, 0), RGB(0, 255, 0), RGB(0, 0, 255), RGB(255, 255, 0) };
    PIXELFORMATDESCRIPTOR pfd = { sizeof(pfd), 1, PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER,
                                  PFD_TYPE_RGBA, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 24 };
    WNDCLASSW wc = { 0, proc, 0, 0, inst, NULL, NULL, (HBRUSH)GetStockObject(GRAY_BRUSH), NULL, L"glchild" };
    int x = GetSystemMetrics(SM_CXSCREEN) - 180, y = GetSystemMetrics(SM_CYSCREEN) - 220;
    int i, same = 0, stale = 0, other = 0;
    char path[MAX_PATH], *slash;
    HWND top, child;
    HGLRC ctx;
    HDC dc, screen;
    POINT pt = { 40, 40 };
    FILE *out;

    GetModuleFileNameA(NULL, path, MAX_PATH);
    if ((slash = strrchr(path, '\\'))) strcpy(slash + 1, "glchild.log");
    out = fopen(path, "w");
    RegisterClassW(&wc);
    top = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_TOPMOST, L"glchild", L"glchild test", WS_POPUP | WS_VISIBLE,
                          x, y, 160, 160, NULL, NULL, inst, NULL);
    child = CreateWindowW(L"glchild", NULL, WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS, 20, 20, 120, 120,
                          top, NULL, inst, NULL);
    dc = GetDC(child);
    SetPixelFormat(dc, ChoosePixelFormat(dc, &pfd), &pfd);
    ctx = wglCreateContext(dc);
    wglMakeCurrent(dc, ctx);
    fprintf(out, "renderer: %s\n", glGetString(GL_RENDERER));
    if (cmd && wcsstr(cmd, L"novsync")) {          /* wglSwapIntervalEXT(0) */
        BOOL (WINAPI *interval)(int) = (void *)wglGetProcAddress("wglSwapIntervalEXT");
        fprintf(out, "swap interval 0: %d\n", interval ? interval(0) : -1);
    }
    for (i = 0; i < 6; i++) { glClear(GL_COLOR_BUFFER_BIT); SwapBuffers(dc); pump(); Sleep(30); }
    ClientToScreen(child, &pt);
    screen = GetDC(NULL);
    for (i = 0; i < 40; i++) {
        COLORREF want = colors[i % 4], prev = colors[(i + 3) % 4], got;
        glClearColor(GetRValue(want) / 255.f, GetGValue(want) / 255.f, GetBValue(want) / 255.f, 1);
        glClear(GL_COLOR_BUFFER_BIT);
        SwapBuffers(dc);
        pump();
        Sleep(40);                  /* idle, like an app waiting for the next event */
        got = GetPixel(screen, pt.x, pt.y) & 0xffffff;
        if (got == want) same++; else if (i && got == prev) stale++; else other++;
    }
    fprintf(out, "frames 40: current %d, previous frame %d, other %d\n", same, stale, other);
    fclose(out);
    wglMakeCurrent(NULL, NULL);
    wglDeleteContext(ctx);
    DestroyWindow(top);
    return 0;
}
