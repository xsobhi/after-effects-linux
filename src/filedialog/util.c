/* String, path and process helpers for filedialog.dll. */
#include "fd.h"

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
