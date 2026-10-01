/* filedialog.dll: IFileOpenDialog / IFileSaveDialog backed by the desktop's file chooser.
 *
 * Registered (per user, in the Adobe prefix) as the COM server for CLSID_FileOpenDialog
 * and CLSID_FileSaveDialog. Show() hands the request to lib/filechooser.py, which asks
 * xdg-desktop-portal for the native dialog; if that is unavailable it falls back to
 * Wine's own dialog from comdlg32.
 */
#ifndef FD_H
#define FD_H

#define COBJMACROS
#define CINTERFACE
#include <windows.h>
#include <shobjidl.h>
#include <shlobj.h>

#define FD_MAX_CONTROLS 96
#define FD_MAX_ITEMS 128
#define FD_MAX_SINKS 16

enum ctl_type { CTL_CHECK, CTL_COMBO, CTL_RADIO, CTL_MENU, CTL_TEXT, CTL_EDIT,
                CTL_BUTTON, CTL_SEPARATOR };

struct ctl_item { DWORD id; WCHAR *label; };

struct control {
    DWORD id;
    enum ctl_type type;
    WCHAR *label, *group, *text;
    BOOL checked;
    DWORD selected, state;
    struct ctl_item items[FD_MAX_ITEMS];
    int nitems;
};

struct dialog {
    const void *vtbl;                       /* IFileOpenDialog or IFileSaveDialog */
    const void *cust_vtbl;                  /* IFileDialogCustomize */
    LONG ref;
    BOOL save;
    FILEOPENDIALOGOPTIONS options;
    COMDLG_FILTERSPEC *filters;
    UINT nfilters, filter_index;            /* filter_index is 1-based, as in the API */
    WCHAR *title, *ok_label, *file_name, *default_ext, *folder, *default_folder;
    IFileDialogEvents *sinks[FD_MAX_SINKS];
    struct control controls[FD_MAX_CONTROLS];
    int ncontrols;
    WCHAR *group;                           /* label of the open visual group */
    WCHAR **results;                        /* Windows paths chosen by the user */
    int nresults;
};

/* main.c */
extern LONG fd_objects;
HRESULT fd_create(BOOL save, REFIID riid, void **out);

/* dialog.c / results.c */
extern const void *fd_open_vtbl, *fd_save_vtbl;
HRESULT STDMETHODCALLTYPE fd_QueryInterface(void *iface, REFIID riid, void **out);
ULONG STDMETHODCALLTYPE fd_AddRef(void *iface);
ULONG STDMETHODCALLTYPE fd_Release(void *iface);
void fd_set_results(struct dialog *d, WCHAR **paths, int n);

/* customize.c */
extern const void *fd_cust_vtbl;
struct control *fd_control(struct dialog *d, DWORD id);
void fd_free_controls(struct dialog *d);

/* show.c / fallback.c */
HRESULT STDMETHODCALLTYPE fd_Show(void *iface, HWND owner);
HRESULT fd_show_wine(struct dialog *d, HWND owner);

/* util.c */
void fd_log(const char *fmt, ...);
const char *fd_guid(REFGUID g);
WCHAR *fd_strdup(const WCHAR *s);
void fd_setstr(WCHAR **dst, const WCHAR *src);
WCHAR *fd_cotask_strdup(const WCHAR *s);
char *fd_utf8(const WCHAR *s);
WCHAR *fd_wide(const char *s);
char *fd_unix_path(const WCHAR *dos);
WCHAR *fd_dos_path(const char *unix_path);
WCHAR *fd_item_path(IShellItem *item);
HRESULT fd_item_from_path(const WCHAR *path, IShellItem **out);
BOOL fd_spawn(char *const argv[]);

static inline struct dialog *fd_from_iface(void *iface) { return (struct dialog *)iface; }
static inline struct dialog *fd_from_cust(void *iface)
{
    return CONTAINING_RECORD(iface, struct dialog, cust_vtbl);
}

#endif
