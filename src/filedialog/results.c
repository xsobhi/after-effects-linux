/* Result getters, IFileOpenDialog/IFileSaveDialog extras and the dialog vtables. */
#include "fd.h"

HRESULT STDMETHODCALLTYPE fd_SetFileTypes(void *, UINT, const COMDLG_FILTERSPEC *);
HRESULT STDMETHODCALLTYPE fd_SetFileTypeIndex(void *, UINT);
HRESULT STDMETHODCALLTYPE fd_GetFileTypeIndex(void *, UINT *);
HRESULT STDMETHODCALLTYPE fd_Advise(void *, IFileDialogEvents *, DWORD *);
HRESULT STDMETHODCALLTYPE fd_Unadvise(void *, DWORD);
HRESULT STDMETHODCALLTYPE fd_SetOptions(void *, FILEOPENDIALOGOPTIONS);
HRESULT STDMETHODCALLTYPE fd_GetOptions(void *, FILEOPENDIALOGOPTIONS *);
HRESULT STDMETHODCALLTYPE fd_SetDefaultFolder(void *, IShellItem *);
HRESULT STDMETHODCALLTYPE fd_SetFolder(void *, IShellItem *);
HRESULT STDMETHODCALLTYPE fd_SetFileName(void *, LPCWSTR);
HRESULT STDMETHODCALLTYPE fd_SetTitle(void *, LPCWSTR);
HRESULT STDMETHODCALLTYPE fd_SetOkButtonLabel(void *, LPCWSTR);
HRESULT STDMETHODCALLTYPE fd_SetFileNameLabel(void *, LPCWSTR);
HRESULT STDMETHODCALLTYPE fd_AddPlace(void *, IShellItem *, FDAP);
HRESULT STDMETHODCALLTYPE fd_SetDefaultExtension(void *, LPCWSTR);
HRESULT STDMETHODCALLTYPE fd_Close(void *, HRESULT);
HRESULT STDMETHODCALLTYPE fd_SetClientGuid(void *, REFGUID);
HRESULT STDMETHODCALLTYPE fd_ClearClientData(void *);
HRESULT STDMETHODCALLTYPE fd_SetFilter(void *, IShellItemFilter *);

void fd_set_results(struct dialog *d, WCHAR **paths, int n)
{
    int i;
    for (i = 0; i < d->nresults; i++) HeapFree(GetProcessHeap(), 0, d->results[i]);
    HeapFree(GetProcessHeap(), 0, d->results);
    d->results = paths;
    d->nresults = n;
}

static WCHAR *current_path(struct dialog *d)
{
    return d->nresults ? d->results[0] : NULL;
}

static HRESULT STDMETHODCALLTYPE fd_GetFolder(void *iface, IShellItem **out)
{
    struct dialog *d = fd_from_iface(iface);
    WCHAR *path = current_path(d), dir[MAX_PATH * 2];
    if (path) {
        lstrcpynW(dir, path, ARRAYSIZE(dir));
        if (wcsrchr(dir, '\\')) *wcsrchr(dir, '\\') = 0;
        return fd_item_from_path(dir, out);
    }
    return fd_item_from_path(d->folder ? d->folder : d->default_folder, out);
}

static HRESULT STDMETHODCALLTYPE fd_GetResult(void *iface, IShellItem **out)
{
    struct dialog *d = fd_from_iface(iface);
    if (!out) return E_POINTER;
    *out = NULL;
    return d->nresults ? fd_item_from_path(d->results[0], out) : E_UNEXPECTED;
}

static HRESULT STDMETHODCALLTYPE fd_GetCurrentSelection(void *iface, IShellItem **out)
{
    return fd_GetResult(iface, out);
}

static HRESULT STDMETHODCALLTYPE fd_GetFileName(void *iface, LPWSTR *out)
{
    struct dialog *d = fd_from_iface(iface);
    WCHAR *path = current_path(d);
    if (!out) return E_POINTER;
    if (path) path = wcsrchr(path, '\\') ? wcsrchr(path, '\\') + 1 : path;
    else path = d->file_name;
    *out = fd_cotask_strdup(path ? path : L"");
    return *out ? S_OK : E_OUTOFMEMORY;
}

static HRESULT STDMETHODCALLTYPE fd_GetResults(void *iface, IShellItemArray **out)
{
    struct dialog *d = fd_from_iface(iface);
    PIDLIST_ABSOLUTE pidls[256];
    HRESULT hr = S_OK;
    int i, n = 0;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!d->nresults) return E_UNEXPECTED;
    for (i = 0; i < d->nresults && n < 256; i++)
        if (SUCCEEDED(SHParseDisplayName(d->results[i], NULL, &pidls[n], 0, NULL))) n++;
    if (!n) return E_FAIL;
    hr = SHCreateShellItemArrayFromIDLists(n, (PCIDLIST_ABSOLUTE_ARRAY)pidls, out);
    for (i = 0; i < n; i++) CoTaskMemFree(pidls[i]);
    return hr;
}

static HRESULT STDMETHODCALLTYPE fd_GetSelectedItems(void *iface, IShellItemArray **out)
{
    return fd_GetResults(iface, out);
}

static HRESULT STDMETHODCALLTYPE fd_SetSaveAsItem(void *iface, IShellItem *item)
{
    struct dialog *d = fd_from_iface(iface);
    WCHAR *path = fd_item_path(item), *slash;
    if (!path) return E_INVALIDARG;
    if ((slash = wcsrchr(path, '\\'))) {
        fd_setstr(&d->file_name, slash + 1);
        *slash = 0;
        HeapFree(GetProcessHeap(), 0, d->folder);
        d->folder = path;
    } else {
        HeapFree(GetProcessHeap(), 0, d->file_name);
        d->file_name = path;
    }
    return S_OK;
}

static HRESULT STDMETHODCALLTYPE fd_SetProperties(void *iface, IPropertyStore *store) { return S_OK; }
static HRESULT STDMETHODCALLTYPE fd_SetCollectedProperties(void *iface, IPropertyDescriptionList *l, BOOL b)
{ return S_OK; }
static HRESULT STDMETHODCALLTYPE fd_GetProperties(void *iface, IPropertyStore **store) { return E_NOTIMPL; }
static HRESULT STDMETHODCALLTYPE fd_ApplyProperties(void *iface, IShellItem *i, IPropertyStore *s, HWND w,
                                                    IFileOperationProgressSink *p) { return S_OK; }

/* Method order must match shobjidl.h exactly. */
#define FD_DIALOG_METHODS \
    (void *)fd_QueryInterface, (void *)fd_AddRef, (void *)fd_Release, (void *)fd_Show, \
    (void *)fd_SetFileTypes, (void *)fd_SetFileTypeIndex, (void *)fd_GetFileTypeIndex, \
    (void *)fd_Advise, (void *)fd_Unadvise, (void *)fd_SetOptions, (void *)fd_GetOptions, \
    (void *)fd_SetDefaultFolder, (void *)fd_SetFolder, (void *)fd_GetFolder, \
    (void *)fd_GetCurrentSelection, (void *)fd_SetFileName, (void *)fd_GetFileName, \
    (void *)fd_SetTitle, (void *)fd_SetOkButtonLabel, (void *)fd_SetFileNameLabel, \
    (void *)fd_GetResult, (void *)fd_AddPlace, (void *)fd_SetDefaultExtension, (void *)fd_Close, \
    (void *)fd_SetClientGuid, (void *)fd_ClearClientData, (void *)fd_SetFilter

static const void *const open_methods[] = { FD_DIALOG_METHODS,
    (void *)fd_GetResults, (void *)fd_GetSelectedItems };
static const void *const save_methods[] = { FD_DIALOG_METHODS,
    (void *)fd_SetSaveAsItem, (void *)fd_SetProperties, (void *)fd_SetCollectedProperties,
    (void *)fd_GetProperties, (void *)fd_ApplyProperties };

const void *fd_open_vtbl = open_methods;
const void *fd_save_vtbl = save_methods;
