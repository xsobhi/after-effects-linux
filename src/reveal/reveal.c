/* winereveal.exe PATH - show PATH in the desktop's file manager.
 *
 * Wine's explorer.exe starts this for folder windows, including "explorer /select,FILE"
 * ("Reveal in Explorer", Media Encoder's output links): see patches/0013. A file is shown
 * selected in its folder through org.freedesktop.FileManager1 (Nemo, Nautilus, Dolphin,
 * Caja, ...), a folder is opened; without that D-Bus service xdg-open opens the folder. */
#include <windows.h>

typedef int (*spawn_fn)(char *const argv[], int wait);
typedef char *(CDECL *unix_name_fn)(const WCHAR *dos);

/* file:// URI of a Unix path: everything but unreserved characters and '/' escaped */
static void to_uri(const char *path, char *uri, size_t size)
{
    static const char hex[] = "0123456789ABCDEF";
    size_t n = 0;

    lstrcpyA(uri, "file://");
    n = 7;
    for (const unsigned char *p = (const unsigned char *)path; *p && n + 4 < size; p++) {
        if ((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') || (*p >= '0' && *p <= '9') ||
            *p == '/' || *p == '-' || *p == '_' || *p == '.' || *p == '~') {
            uri[n++] = *p;
        } else {
            uri[n++] = '%'; uri[n++] = hex[*p >> 4]; uri[n++] = hex[*p & 15];
        }
    }
    uri[n] = 0;
}

/* the command line after the program name, without surrounding quotes */
static WCHAR *argument(void)
{
    WCHAR *p = GetCommandLineW(), *end;

    if (*p == '"') {
        p++;
        while (*p && *p != '"') p++;
        if (*p) p++;
    }
    else while (*p && *p != ' ' && *p != '\t') p++;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '"') p++;
    end = p + lstrlenW(p);
    while (end > p && (end[-1] == '"' || end[-1] == ' ' || end[-1] == '\t')) *--end = 0;
    return p;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, WCHAR *cmdline, int show)
{
    static const char script[] =
        "gdbus call --session --dest org.freedesktop.FileManager1 "
        "--object-path /org/freedesktop/FileManager1 "
        "--method \"org.freedesktop.FileManager1.$1\" \"['$2']\" '' >/dev/null 2>&1 "
        "|| exec xdg-open \"$3\"";
    spawn_fn spawn = (spawn_fn)GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "__wine_unix_spawnvp");
    unix_name_fn unix_name = (unix_name_fn)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),
                                                         "wine_get_unix_file_name");
    WCHAR *path = argument();
    DWORD attrs = GetFileAttributesW(path);
    char *unix_path, dir[MAX_PATH * 3], uri[MAX_PATH * 9], *slash;
    BOOL is_dir = attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_DIRECTORY);

    if (!*path || attrs == INVALID_FILE_ATTRIBUTES || !spawn || !unix_name) return 1;
    if (!(unix_path = unix_name(path)) || lstrlenA(unix_path) >= (int)sizeof(dir)) return 1;
    to_uri(unix_path, uri, sizeof(uri));
    lstrcpyA(dir, unix_path);
    if (!is_dir && (slash = strrchr(dir, '/')) && slash != dir) *slash = 0;

    char *argv[] = { "/usr/bin/env", "-u", "LD_LIBRARY_PATH", "-u", "GST_PLUGIN_SYSTEM_PATH_1_0",
                     "/bin/sh", "-c", (char *)script, "winereveal",
                     is_dir ? "ShowFolders" : "ShowItems", uri, dir, NULL };
    return spawn(argv, FALSE) ? 1 : 0;
}
