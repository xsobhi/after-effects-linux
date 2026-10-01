/* Drag-and-drop test target: a window with an OLE IDropTarget, like After Effects' panels.
 * Logs every DragEnter/DragOver/Drop and the dropped file names to dndtest.log next to
 * the exe.  Build: zig cc -target x86_64-windows-gnu -o dndtest.exe dndtest.c -lole32 -lshell32 -luser32 -lgdi32 */
#define COBJMACROS
#include <windows.h>
#include <ole2.h>
#include <shellapi.h>
#include <stdio.h>

static FILE *out;
static HWND win;
static WCHAR shown[4096] = L"Drop files here";

static void log_formats(IDataObject *data)
{
    IEnumFORMATETC *e;
    FORMATETC f;
    char name[128];
    if (FAILED(IDataObject_EnumFormatEtc(data, DATADIR_GET, &e))) { fprintf(out, "  EnumFormatEtc failed\n"); return; }
    while (IEnumFORMATETC_Next(e, 1, &f, NULL) == S_OK) {
        if (!GetClipboardFormatNameA(f.cfFormat, name, sizeof(name))) sprintf(name, "#%u", f.cfFormat);
        fprintf(out, "  format %s tymed %lu\n", name, f.tymed);
    }
    IEnumFORMATETC_Release(e);
}

static HRESULT STDMETHODCALLTYPE QI(IDropTarget *t, REFIID iid, void **o)
{
    if (IsEqualIID(iid, &IID_IUnknown) || IsEqualIID(iid, &IID_IDropTarget)) { *o = t; return S_OK; }
    *o = NULL; return E_NOINTERFACE;
}
static ULONG STDMETHODCALLTYPE AddRef(IDropTarget *t) { return 2; }
static ULONG STDMETHODCALLTYPE Release(IDropTarget *t) { return 1; }

static HRESULT STDMETHODCALLTYPE DragEnter(IDropTarget *t, IDataObject *d, DWORD keys, POINTL pt, DWORD *eff)
{
    fprintf(out, "DragEnter at %ld,%ld keys %#lx allowed %#lx\n", pt.x, pt.y, keys, *eff);
    log_formats(d);
    *eff &= DROPEFFECT_COPY | DROPEFFECT_LINK;
    fflush(out);
    return S_OK;
}
static HRESULT STDMETHODCALLTYPE DragOver(IDropTarget *t, DWORD keys, POINTL pt, DWORD *eff)
{
    *eff &= DROPEFFECT_COPY | DROPEFFECT_LINK;
    return S_OK;
}
static HRESULT STDMETHODCALLTYPE DragLeave(IDropTarget *t) { fprintf(out, "DragLeave\n"); fflush(out); return S_OK; }
static HRESULT STDMETHODCALLTYPE Drop(IDropTarget *t, IDataObject *d, DWORD keys, POINTL pt, DWORD *eff)
{
    FORMATETC f = { CF_HDROP, NULL, DVASPECT_CONTENT, -1, TYMED_HGLOBAL };
    STGMEDIUM m;
    UINT i, n;
    WCHAR file[MAX_PATH];
    fprintf(out, "Drop at %ld,%ld allowed %#lx\n", pt.x, pt.y, *eff);
    shown[0] = 0;
    if (SUCCEEDED(IDataObject_GetData(d, &f, &m))) {
        n = DragQueryFileW(m.hGlobal, ~0u, NULL, 0);
        for (i = 0; i < n; i++) {
            DragQueryFileW(m.hGlobal, i, file, MAX_PATH);
            fprintf(out, "  file %ls\n", file);
            wcsncat(shown, file, 4000 - wcslen(shown)); wcscat(shown, L"\n");
        }
        ReleaseStgMedium(&m);
    } else fprintf(out, "  no CF_HDROP\n");
    *eff = DROPEFFECT_COPY;
    fflush(out);
    InvalidateRect(win, NULL, TRUE);
    return S_OK;
}

static IDropTargetVtbl vtbl = { QI, AddRef, Release, DragEnter, DragOver, DragLeave, Drop };
static IDropTarget target = { &vtbl };

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_PAINT) {
        PAINTSTRUCT ps; RECT r;
        HDC dc = BeginPaint(h, &ps);
        GetClientRect(h, &r);
        DrawTextW(dc, shown, -1, &r, DT_CENTER);
        EndPaint(h, &ps);
        return 0;
    }
    if (msg == WM_DESTROY) PostQuitMessage(0);
    return DefWindowProcW(h, msg, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, LPWSTR cmd, int show)
{
    WNDCLASSW wc = { 0, proc, 0, 0, inst, NULL, LoadCursor(NULL, IDC_ARROW), (HBRUSH)(COLOR_WINDOW + 1), NULL, L"dndtest" };
    char path[MAX_PATH], *slash;
    MSG msg;
    GetModuleFileNameA(NULL, path, MAX_PATH);
    if ((slash = strrchr(path, '\\'))) strcpy(slash + 1, "dndtest.log");
    out = fopen(path, "w");
    OleInitialize(NULL);
    RegisterClassW(&wc);
    win = CreateWindowW(L"dndtest", L"dndtest", WS_OVERLAPPEDWINDOW | WS_VISIBLE, 100, 100, 500, 300,
                        NULL, NULL, inst, NULL);
    fprintf(out, "RegisterDragDrop -> %#lx\n", RegisterDragDrop(win, &target));
    fflush(out);
    while (GetMessageW(&msg, NULL, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    RevokeDragDrop(win);
    OleUninitialize();
    return 0;
}
