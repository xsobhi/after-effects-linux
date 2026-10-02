/* Sampling profiler for a running Windows process under Wine: suspends one thread (the main
 * thread by default) every few ms, walks its stack with dbghelp and prints one line per
 * sample: "frame0 < frame1 < ...". dev/profile_report.py aggregates the output.
 *   stacksnap.exe PID|NAME.exe SECONDS [INTERVAL_MS] [all]     ("all" = every thread)
 * Build: zig cc -target x86_64-windows-gnu -O2 -o stacksnap.exe stacksnap.c -ldbghelp */
#include <windows.h>
#include <dbghelp.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>

#define MAX_THREADS 512
#define MAX_FRAMES 48

static HANDLE proc;

static DWORD find_process(const char *arg)
{
    PROCESSENTRY32 pe = { sizeof(pe) };
    HANDLE snap;
    DWORD pid = 0;

    if (arg[0] >= '0' && arg[0] <= '9') return strtoul(arg, NULL, 0);
    snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (Process32First(snap, &pe))
        do if (!_stricmp(pe.szExeFile, arg)) pid = pe.th32ProcessID;
        while (!pid && Process32Next(snap, &pe));
    CloseHandle(snap);
    return pid;
}

static void print_frame(DWORD64 addr)
{
    char buf[sizeof(SYMBOL_INFO) + 256];
    SYMBOL_INFO *sym = (SYMBOL_INFO *)buf;
    IMAGEHLP_MODULE64 mod = { sizeof(mod) };
    DWORD64 disp = 0;
    const char *name = SymGetModuleInfo64(proc, addr, &mod) ? mod.ModuleName : "?";

    sym->SizeOfStruct = sizeof(SYMBOL_INFO);
    sym->MaxNameLen = 255;
    if (SymFromAddr(proc, addr, &disp, sym) && disp < 0x100000)
        printf("%s!%s+0x%llx", name, sym->Name, (unsigned long long)disp);
    else
        printf("%s+0x%llx", name, (unsigned long long)(addr - mod.BaseOfImage));
}

static void sample(HANDLE thread, DWORD tid)
{
    CONTEXT ctx = { 0 };
    STACKFRAME64 frame = { 0 };
    int n;

    if (SuspendThread(thread) == (DWORD)-1) return;
    ctx.ContextFlags = CONTEXT_FULL;
    if (!GetThreadContext(thread, &ctx)) { ResumeThread(thread); return; }
    frame.AddrPC.Offset = ctx.Rip;    frame.AddrPC.Mode = AddrModeFlat;
    frame.AddrStack.Offset = ctx.Rsp; frame.AddrStack.Mode = AddrModeFlat;
    frame.AddrFrame.Offset = ctx.Rbp; frame.AddrFrame.Mode = AddrModeFlat;
    printf("%04lx ", tid);
    for (n = 0; n < MAX_FRAMES; n++) {
        if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, proc, thread, &frame, &ctx, NULL,
                         SymFunctionTableAccess64, SymGetModuleBase64, NULL) || !frame.AddrPC.Offset)
            break;
        if (n) printf(" < ");
        print_frame(frame.AddrPC.Offset);
    }
    ResumeThread(thread);
    printf("\n");
}

int main(int argc, char **argv)
{
    DWORD pid, tids[MAX_THREADS], start;
    HANDLE threads[MAX_THREADS];
    int nthreads = 0, interval, all, i;
    THREADENTRY32 te = { sizeof(te) };
    HANDLE snap;

    if (argc < 3) { fprintf(stderr, "usage: stacksnap PID|NAME.exe SECONDS [INTERVAL_MS] [all]\n"); return 2; }
    if (!(pid = find_process(argv[1]))) { fprintf(stderr, "no process %s\n", argv[1]); return 1; }
    interval = argc > 3 ? atoi(argv[3]) : 20;
    all = argc > 4 && !strcmp(argv[4], "all");
    if (!(proc = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid))) { fprintf(stderr, "OpenProcess failed\n"); return 1; }
    SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
    if (!SymInitialize(proc, NULL, TRUE)) { fprintf(stderr, "SymInitialize failed\n"); return 1; }

    snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (Thread32First(snap, &te))
        do {
            if (te.th32OwnerProcessID != pid || nthreads >= MAX_THREADS) continue;
            if ((threads[nthreads] = OpenThread(THREAD_ALL_ACCESS, FALSE, te.th32ThreadID)))
                tids[nthreads++] = te.th32ThreadID;
            if (!all && nthreads) break;          /* first thread listed = main thread */
        } while (Thread32Next(snap, &te));
    CloseHandle(snap);
    fprintf(stderr, "sampling %d thread(s) of %lu every %d ms\n", nthreads, pid, interval);

    start = GetTickCount();
    while (GetTickCount() - start < (DWORD)atoi(argv[2]) * 1000) {
        for (i = 0; i < nthreads; i++) sample(threads[i], tids[i]);
        fflush(stdout);
        Sleep(interval);
    }
    SymCleanup(proc);
    return 0;
}
