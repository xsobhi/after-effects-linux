/* IModalWindow::Show: ask lib/filechooser.py for the desktop's file chooser. */
#include "fd.h"
#include <stdio.h>

static void put(HANDLE f, const char *key, const WCHAR *value)
{
    char *v = fd_utf8(value), *p;
    DWORD written;
    WriteFile(f, key, lstrlenA(key), &written, NULL);
    WriteFile(f, "=", 1, &written, NULL);
    for (p = v; p && *p; p++) {
        if (*p == '\n') WriteFile(f, "\\n", 2, &written, NULL);
        else if (*p == '\\') WriteFile(f, "\\\\", 2, &written, NULL);
        else if (*p != '\r') WriteFile(f, p, 1, &written, NULL);
    }
    WriteFile(f, "\n", 1, &written, NULL);
    HeapFree(GetProcessHeap(), 0, v);
}

static const WCHAR *control_label(struct dialog *d, int i)
{
    struct control *c = &d->controls[i];
    if (c->label && *c->label) return c->label;
    if (i > 0 && d->controls[i - 1].type == CTL_TEXT && d->controls[i - 1].label)
        return d->controls[i - 1].label;          /* "Import As:" text before a combo */
    return c->group ? c->group : L"";
}

static void put_choices(HANDLE f, struct dialog *d)
{
    WCHAR buf[4096];
    int i, j, len;
    for (i = 0; i < d->ncontrols; i++) {
        struct control *c = &d->controls[i];
        if (!(c->state & CDCS_VISIBLE)) continue;
        if (c->type == CTL_CHECK)
            swprintf(buf, ARRAYSIZE(buf), L"%lu\t%ls\t%ls", c->id, control_label(d, i),
                     c->checked ? L"true" : L"false");
        else if ((c->type == CTL_COMBO || c->type == CTL_RADIO) && c->nitems) {
            len = swprintf(buf, ARRAYSIZE(buf), L"%lu\t%ls\t%lu\t", c->id, control_label(d, i), c->selected);
            for (j = 0; j < c->nitems && len > 0 && len < 3900; j++)
                len += swprintf(buf + len, ARRAYSIZE(buf) - len, L"%ls%lu:%ls", j ? L"|" : L"",
                                c->items[j].id, c->items[j].label);
        } else continue;
        put(f, "choice", buf);
    }
}

static BOOL write_request(struct dialog *d, HWND owner, const WCHAR *path)
{
    HANDLE f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    WCHAR buf[1024], *folder = d->folder ? d->folder : d->default_folder;
    char *unix_folder = fd_unix_path(folder);
    HWND root = owner ? GetAncestor(owner, GA_ROOT) : NULL;
    ULONG_PTR xid = root ? (ULONG_PTR)GetPropA(root, "__wine_x11_whole_window") : 0;
    UINT i;
    if (f == INVALID_HANDLE_VALUE) return FALSE;
    put(f, "mode", (d->options & FOS_PICKFOLDERS) ? L"folder" : d->save ? L"save" : L"open");
    put(f, "multiple", (d->options & FOS_ALLOWMULTISELECT) ? L"1" : L"0");
    put(f, "title", d->title);
    put(f, "accept", d->ok_label);
    if (xid) { swprintf(buf, ARRAYSIZE(buf), L"x11:%lx", (unsigned long)xid); put(f, "parent", buf); }
    if (unix_folder) {
        WCHAR *w = fd_wide(unix_folder);
        put(f, "folder", w);
        HeapFree(GetProcessHeap(), 0, w);
        HeapFree(GetProcessHeap(), 0, unix_folder);
    }
    if (d->file_name) put(f, "name", d->file_name);
    for (i = 0; i < d->nfilters; i++) {
        swprintf(buf, ARRAYSIZE(buf), L"%ls\t%ls", d->filters[i].pszName, d->filters[i].pszSpec);
        put(f, "filter", buf);
    }
    swprintf(buf, ARRAYSIZE(buf), L"%u", d->filter_index ? d->filter_index - 1 : 0);
    put(f, "filter_index", buf);
    put_choices(f, d);
    CloseHandle(f);
    return TRUE;
}

/* Windows adds the selected type's extension when the user types a bare name. */
static WCHAR *with_extension(struct dialog *d, WCHAR *path)
{
    const WCHAR *spec = (d->filter_index && d->filter_index <= d->nfilters)
                        ? d->filters[d->filter_index - 1].pszSpec : NULL;
    const WCHAR *name = wcsrchr(path, '\\') ? wcsrchr(path, '\\') + 1 : path, *ext = NULL;
    WCHAR *r;
    if (wcschr(name, '.')) return path;
    if (spec && !wcsncmp(spec, L"*.", 2) && spec[2] != '*') ext = spec + 1;
    else if (d->default_ext && *d->default_ext) ext = d->default_ext;
    if (!ext) return path;
    r = HeapAlloc(GetProcessHeap(), 0, (lstrlenW(path) + lstrlenW(ext) + 3) * sizeof(WCHAR));
    swprintf(r, lstrlenW(path) + lstrlenW(ext) + 3, L"%ls%ls%.*ls", path, *ext == '.' ? L"" : L".",
             (int)(wcschr(ext, ';') ? wcschr(ext, ';') - ext : lstrlenW(ext)), ext);
    HeapFree(GetProcessHeap(), 0, path);
    return r;
}

static int read_result(struct dialog *d, const WCHAR *path)
{
    FILE *f = _wfopen(path, L"rb");
    char line[8192];
    WCHAR **paths = NULL;
    int response = 2, n = 0;
    if (!f) return 2;
    while (fgets(line, sizeof(line), f)) {
        char *v = strchr(line, '='), *tab;
        if (!v) continue;
        *v++ = 0;
        v[strcspn(v, "\n")] = 0;
        if (!strcmp(line, "response")) response = atoi(v);
        else if (!strcmp(line, "filter_index")) d->filter_index = atoi(v) + 1;
        else if (!strcmp(line, "path") && *v) {
            WCHAR *dos = fd_dos_path(v), *copy = fd_strdup(dos), **grown;
            HeapFree(GetProcessHeap(), 0, dos);
            grown = paths ? HeapReAlloc(GetProcessHeap(), 0, paths, (n + 1) * sizeof(*paths))
                          : HeapAlloc(GetProcessHeap(), 0, sizeof(*paths));
            if (!copy || !grown) { HeapFree(GetProcessHeap(), 0, copy); if (grown) paths = grown; continue; }
            paths = grown;
            paths[n++] = d->save ? with_extension(d, copy) : copy;
        } else if (!strcmp(line, "choice") && (tab = strchr(v, '\t'))) {
            struct control *c;
            *tab++ = 0;
            if (!(c = fd_control(d, strtoul(v, NULL, 10)))) continue;
            if (c->type == CTL_CHECK) c->checked = !strcmp(tab, "true");
            else c->selected = strtoul(tab, NULL, 10);
        }
    }
    fclose(f);
    fd_set_results(d, paths, n);
    return (response == 0 && !n) ? 1 : response;
}

static int run_portal(struct dialog *d, HWND owner)
{
    WCHAR tmp[MAX_PATH], req[MAX_PATH], res[MAX_PATH], helper[MAX_PATH];
    char *ureq, *ures, *uhelper;
    HWND root = owner ? GetAncestor(owner, GA_ROOT) : NULL;
    int response = 2;
    MSG msg;
    if (!GetEnvironmentVariableW(L"ADOBE_FILECHOOSER", helper, ARRAYSIZE(helper))) return 2;
    GetTempPathW(ARRAYSIZE(tmp), tmp);
    swprintf(req, ARRAYSIZE(req), L"%lsfiledialog-%lu-%lu.req", tmp, GetCurrentProcessId(), GetTickCount());
    swprintf(res, ARRAYSIZE(res), L"%lsfiledialog-%lu-%lu.res", tmp, GetCurrentProcessId(), GetTickCount());
    if (!write_request(d, owner, req)) return 2;
    ureq = fd_unix_path(req); ures = fd_unix_path(res); uhelper = fd_utf8(helper);
    if (ureq && ures && uhelper) {
        /* Proton's bundled libraries must not leak into the system Python. */
        char *argv[] = { "/usr/bin/env", "-u", "LD_LIBRARY_PATH", "-u", "GST_PLUGIN_SYSTEM_PATH_1_0",
                         "python3", uhelper, ureq, ures, NULL };
        WCHAR started[MAX_PATH + 16];
        DWORD deadline = GetTickCount() + 15000;
        swprintf(started, ARRAYSIZE(started), L"%ls.started", res);
        if (fd_spawn(argv)) {
            if (root) EnableWindow(root, FALSE);
            /* Keep the app painting and responsive while the dialog is up. */
            while (GetFileAttributesW(res) == INVALID_FILE_ATTRIBUTES) {
                if (GetTickCount() > deadline && GetFileAttributesW(started) == INVALID_FILE_ATTRIBUTES)
                    break;                              /* helper never came up */
                MsgWaitForMultipleObjects(0, NULL, FALSE, 50, QS_ALLINPUT);
                while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
                    if (msg.message == WM_QUIT) { PostQuitMessage((int)msg.wParam); break; }
                    TranslateMessage(&msg);
                    DispatchMessageW(&msg);
                }
            }
            if (root) { EnableWindow(root, TRUE); SetForegroundWindow(root); }
            response = read_result(d, res);
        }
    }
    DeleteFileW(req); DeleteFileW(res);
    HeapFree(GetProcessHeap(), 0, ureq); HeapFree(GetProcessHeap(), 0, ures);
    HeapFree(GetProcessHeap(), 0, uhelper);
    return response;
}

HRESULT STDMETHODCALLTYPE fd_Show(void *iface, HWND owner)
{
    struct dialog *d = fd_from_iface(iface);
    int tries, i, response = 2;
    for (tries = 0; tries < 5; tries++) {
        BOOL rejected = FALSE;
        response = run_portal(d, owner);
        fd_log("Show: portal response %d, %d result(s)", response, d->nresults);
        if (response == 2) return fd_show_wine(d, owner);
        if (response != 0) return HRESULT_FROM_WIN32(ERROR_CANCELLED);
        for (i = 0; i < FD_MAX_SINKS; i++)  /* let the app validate, as Windows does */
            if (d->sinks[i] && IFileDialogEvents_OnFileOk(d->sinks[i], (IFileDialog *)&d->vtbl) == S_FALSE)
                rejected = TRUE;
        if (!rejected) return S_OK;
    }
    return HRESULT_FROM_WIN32(ERROR_CANCELLED);
}
