/* IUnknown + IFileDialog state handling. Vtables live in results.c. */
#include "fd.h"

HRESULT STDMETHODCALLTYPE fd_QueryInterface(void *iface, REFIID riid, void **out)
{
    struct dialog *d = fd_from_iface(iface);
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualIID(riid, &IID_IUnknown) || IsEqualIID(riid, &IID_IModalWindow) ||
        IsEqualIID(riid, &IID_IFileDialog) ||
        IsEqualIID(riid, d->save ? &IID_IFileSaveDialog : &IID_IFileOpenDialog))
        *out = &d->vtbl;
    else if (IsEqualIID(riid, &IID_IFileDialogCustomize))
        *out = &d->cust_vtbl;
    else
        return E_NOINTERFACE;
    fd_AddRef(&d->vtbl);
    return S_OK;
}

ULONG STDMETHODCALLTYPE fd_AddRef(void *iface)
{
    return InterlockedIncrement(&fd_from_iface(iface)->ref);
}

ULONG STDMETHODCALLTYPE fd_Release(void *iface)
{
    struct dialog *d = fd_from_iface(iface);
    ULONG ref = InterlockedDecrement(&d->ref);
    UINT i;
    if (ref) return ref;
    for (i = 0; i < FD_MAX_SINKS; i++)
        if (d->sinks[i]) IFileDialogEvents_Release(d->sinks[i]);
    for (i = 0; i < d->nfilters; i++) {
        HeapFree(GetProcessHeap(), 0, (void *)d->filters[i].pszName);
        HeapFree(GetProcessHeap(), 0, (void *)d->filters[i].pszSpec);
    }
    HeapFree(GetProcessHeap(), 0, d->filters);
    WCHAR **strs[] = { &d->title, &d->ok_label, &d->file_name, &d->default_ext, &d->folder,
                       &d->default_folder, &d->group };
    for (i = 0; i < ARRAYSIZE(strs); i++) HeapFree(GetProcessHeap(), 0, *strs[i]);
    fd_set_results(d, NULL, 0);
    fd_free_controls(d);
    HeapFree(GetProcessHeap(), 0, d);
    InterlockedDecrement(&fd_objects);
    return 0;
}

HRESULT STDMETHODCALLTYPE fd_SetFileTypes(void *iface, UINT n, const COMDLG_FILTERSPEC *specs)
{
    struct dialog *d = fd_from_iface(iface);
    UINT i;
    if (!specs || !n) return E_INVALIDARG;
    if (d->filters) return E_UNEXPECTED;    /* Windows allows this only once */
    if (!(d->filters = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n * sizeof(*specs))))
        return E_OUTOFMEMORY;
    for (i = 0; i < n; i++) {
        d->filters[i].pszName = fd_strdup(specs[i].pszName ? specs[i].pszName : L"");
        d->filters[i].pszSpec = fd_strdup(specs[i].pszSpec ? specs[i].pszSpec : L"*.*");
    }
    d->nfilters = n;
    if (!d->filter_index) d->filter_index = 1;
    return S_OK;
}

HRESULT STDMETHODCALLTYPE fd_SetFileTypeIndex(void *iface, UINT index)
{
    fd_from_iface(iface)->filter_index = index ? index : 1;
    return S_OK;
}

HRESULT STDMETHODCALLTYPE fd_GetFileTypeIndex(void *iface, UINT *index)
{
    if (!index) return E_POINTER;
    *index = fd_from_iface(iface)->filter_index;
    return S_OK;
}

HRESULT STDMETHODCALLTYPE fd_Advise(void *iface, IFileDialogEvents *sink, DWORD *cookie)
{
    struct dialog *d = fd_from_iface(iface);
    DWORD i;
    if (!sink || !cookie) return E_INVALIDARG;
    for (i = 0; i < FD_MAX_SINKS; i++)
        if (!d->sinks[i]) {
            IFileDialogEvents_AddRef(sink);
            d->sinks[i] = sink;
            *cookie = i + 1;
            return S_OK;
        }
    return E_OUTOFMEMORY;
}

HRESULT STDMETHODCALLTYPE fd_Unadvise(void *iface, DWORD cookie)
{
    struct dialog *d = fd_from_iface(iface);
    if (!cookie || cookie > FD_MAX_SINKS || !d->sinks[cookie - 1]) return E_INVALIDARG;
    IFileDialogEvents_Release(d->sinks[cookie - 1]);
    d->sinks[cookie - 1] = NULL;
    return S_OK;
}

HRESULT STDMETHODCALLTYPE fd_SetOptions(void *iface, FILEOPENDIALOGOPTIONS opts)
{
    fd_from_iface(iface)->options = opts;
    return S_OK;
}

HRESULT STDMETHODCALLTYPE fd_GetOptions(void *iface, FILEOPENDIALOGOPTIONS *opts)
{
    if (!opts) return E_POINTER;
    *opts = fd_from_iface(iface)->options;
    return S_OK;
}

static HRESULT set_folder(WCHAR **dst, IShellItem *item)
{
    WCHAR *path = fd_item_path(item);
    if (!path) return E_INVALIDARG;
    HeapFree(GetProcessHeap(), 0, *dst);
    *dst = path;
    return S_OK;
}

HRESULT STDMETHODCALLTYPE fd_SetDefaultFolder(void *iface, IShellItem *item)
{
    return set_folder(&fd_from_iface(iface)->default_folder, item);
}

HRESULT STDMETHODCALLTYPE fd_SetFolder(void *iface, IShellItem *item)
{
    return set_folder(&fd_from_iface(iface)->folder, item);
}

#define SETTER(name, field) \
    HRESULT STDMETHODCALLTYPE fd_##name(void *iface, LPCWSTR s) \
    { fd_setstr(&fd_from_iface(iface)->field, s); return S_OK; }
SETTER(SetFileName, file_name)
SETTER(SetTitle, title)
SETTER(SetOkButtonLabel, ok_label)
SETTER(SetDefaultExtension, default_ext)

/* Accepted for compatibility; the native dialog has no equivalent. */
HRESULT STDMETHODCALLTYPE fd_SetFileNameLabel(void *iface, LPCWSTR s) { return S_OK; }
HRESULT STDMETHODCALLTYPE fd_AddPlace(void *iface, IShellItem *item, FDAP fdap) { return S_OK; }
HRESULT STDMETHODCALLTYPE fd_Close(void *iface, HRESULT hr) { return S_OK; }
HRESULT STDMETHODCALLTYPE fd_SetClientGuid(void *iface, REFGUID guid) { return S_OK; }
HRESULT STDMETHODCALLTYPE fd_ClearClientData(void *iface) { return S_OK; }
HRESULT STDMETHODCALLTYPE fd_SetFilter(void *iface, IShellItemFilter *filter) { return S_OK; }
