/* String, path, logging and process helpers for filedialog.dll. */
#include "fd.h"
#include <stdarg.h>
#include <stdio.h>

/* Set ADOBE_FILEDIALOG_LOG=1 (or to a Windows file path) to trace calls to
 * %TEMP%\adobe-filedialog.log. */
void fd_log(const char *fmt, ...)
{
    static int enabled = -1;
    static WCHAR path[MAX_PATH];
    char buf[1024];
    va_list args;
    HANDLE f;
    DWORD n;
    if (enabled == -1) {
        WCHAR env[MAX_PATH];
        enabled = GetEnvironmentVariableW(L"ADOBE_FILEDIALOG_LOG", env, MAX_PATH) > 0;
        if (enabled && (env[0] == '1' && !env[1])) {
            GetTempPathW(MAX_PATH, path);
            lstrcatW(path, L"adobe-filedialog.log");
        } else if (enabled) lstrcpynW(path, env, MAX_PATH);
    }
    if (!enabled) return;
    va_start(args, fmt);
    n = vsnprintf(buf, sizeof(buf) - 2, fmt, args);
    va_end(args);
    if (n > sizeof(buf) - 2) n = sizeof(buf) - 2;
    buf[n++] = '\n';
    f = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) return;
    WriteFile(f, buf, n, &n, NULL);
    CloseHandle(f);
}

const char *fd_guid(REFGUID g)
{
    static char buf[4][40];
    static int i;
    char *b = buf[i++ & 3];
    snprintf(b, 40, "{%08lx-%04x-%04x-%02x%02x-%02x%02x%02x%02x%02x%02x}", (unsigned long)g->Data1,
             g->Data2, g->Data3, g->Data4[0], g->Data4[1], g->Data4[2], g->Data4[3], g->Data4[4],
             g->Data4[5], g->Data4[6], g->Data4[7]);
    return b;
}

typedef char *(CDECL *unix_name_fn)(const WCHAR *dos);
typedef WCHAR *(CDECL *dos_name_fn)(const char *unix_path);
typedef NTSTATUS (CDECL *spawn_fn)(char *const argv[], int wait);

WCHAR *fd_strdup(const WCHAR *s)
{
    WCHAR *r;
    size_t n;
    if (!s) return NULL;
    n = (lstrlenW(s) + 1) * sizeof(WCHAR);
    if ((r = HeapAlloc(GetProcessHeap(), 0, n))) memcpy(r, s, n);
    return r;
}

void fd_setstr(WCHAR **dst, const WCHAR *src)
{
    HeapFree(GetProcessHeap(), 0, *dst);
    *dst = fd_strdup(src);
}

WCHAR *fd_cotask_strdup(const WCHAR *s)
{
    WCHAR *r;
    size_t n;
    if (!s) return NULL;
    n = (lstrlenW(s) + 1) * sizeof(WCHAR);
    if ((r = CoTaskMemAlloc(n))) memcpy(r, s, n);
    return r;
}

char *fd_utf8(const WCHAR *s)
{
    int n;
    char *r;
    if (!s) s = L"";
    n = WideCharToMultiByte(CP_UTF8, 0, s, -1, NULL, 0, NULL, NULL);
    if ((r = HeapAlloc(GetProcessHeap(), 0, n)))
        WideCharToMultiByte(CP_UTF8, 0, s, -1, r, n, NULL, NULL);
    return r;
}

WCHAR *fd_wide(const char *s)
{
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    WCHAR *r = HeapAlloc(GetProcessHeap(), 0, n * sizeof(WCHAR));
    if (r) MultiByteToWideChar(CP_UTF8, 0, s, -1, r, n);
    return r;
}

/* Wine exports these from kernel32; results are allocated on the process heap. */
char *fd_unix_path(const WCHAR *dos)
{
    unix_name_fn fn = (unix_name_fn)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),
                                                   "wine_get_unix_file_name");
    return (fn && dos && *dos) ? fn(dos) : NULL;
}

WCHAR *fd_dos_path(const char *unix_path)
{
    dos_name_fn fn = (dos_name_fn)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),
                                                 "wine_get_dos_file_name");
    WCHAR *dos = fn ? fn(unix_path) : NULL;
    /* Paths under the prefix come back as \\?\Z:\...; keep the plain drive form. */
    if (dos && !wcsncmp(dos, L"\\\\?\\", 4)) memmove(dos, dos + 4, (lstrlenW(dos) - 3) * sizeof(WCHAR));
    return dos;
}

WCHAR *fd_item_path(IShellItem *item)
{
    WCHAR *name = NULL, *r;
    if (!item || FAILED(IShellItem_GetDisplayName(item, SIGDN_FILESYSPATH, &name))) return NULL;
    r = fd_strdup(name);
    CoTaskMemFree(name);
    return r;
}

HRESULT fd_item_from_path(const WCHAR *path, IShellItem **out)
{
    PIDLIST_ABSOLUTE pidl;
    HRESULT hr;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!path) return E_FAIL;
    hr = SHCreateItemFromParsingName(path, NULL, &IID_IShellItem, (void **)out);
    if (SUCCEEDED(hr)) return hr;
    /* A file being saved does not exist yet; parsing fails, a simple ID list does not. */
    if (!(pidl = SHSimpleIDListFromPath(path))) return hr;
    hr = SHCreateItemFromIDList(pidl, &IID_IShellItem, (void **)out);
    CoTaskMemFree(pidl);
    return hr;
}

/* Start a native Linux program without waiting (Wine's ntdll export). */
BOOL fd_spawn(char *const argv[])
{
    spawn_fn fn = (spawn_fn)GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "__wine_unix_spawnvp");
    return fn && fn(argv, FALSE) == 0;
}
