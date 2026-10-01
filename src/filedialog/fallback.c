/* Fallback: show Wine's own dialog (comdlg32) when the portal helper is unavailable. */
#include "fd.h"

typedef HRESULT (WINAPI *get_class_fn)(REFCLSID, REFIID, void **);

static IFileDialog *wine_dialog(BOOL save)
{
    HMODULE comdlg = LoadLibraryW(L"comdlg32.dll");
    get_class_fn get = comdlg ? (get_class_fn)GetProcAddress(comdlg, "DllGetClassObject") : NULL;
    IClassFactory *factory = NULL;
    IFileDialog *dialog = NULL;
    REFCLSID clsid = save ? &CLSID_FileSaveDialog : &CLSID_FileOpenDialog;
    if (!get || FAILED(get(clsid, &IID_IClassFactory, (void **)&factory))) return NULL;
    IClassFactory_CreateInstance(factory, NULL, &IID_IFileDialog, (void **)&dialog);
    IClassFactory_Release(factory);
    return dialog;
}

static WCHAR **collect_results(IFileDialog *dialog, BOOL multi, int *n)
{
    IShellItemArray *array = NULL;
    IFileOpenDialog *open = NULL;
    IShellItem *item = NULL;
    WCHAR **paths;
    DWORD count = 1, i;
    *n = 0;
    if (multi && SUCCEEDED(IFileDialog_QueryInterface(dialog, &IID_IFileOpenDialog, (void **)&open))) {
        IFileOpenDialog_GetResults(open, &array);
        IFileOpenDialog_Release(open);
    }
    if (array) IShellItemArray_GetCount(array, &count);
    if (!(paths = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, count * sizeof(*paths)))) return NULL;
    for (i = 0; i < count; i++) {
        if (array) IShellItemArray_GetItemAt(array, i, &item);
        else IFileDialog_GetResult(dialog, &item);
        if (!item) continue;
        if ((paths[*n] = fd_item_path(item))) (*n)++;
        IShellItem_Release(item);
        item = NULL;
    }
    if (array) IShellItemArray_Release(array);
    return paths;
}

HRESULT fd_show_wine(struct dialog *d, HWND owner)
{
    IFileDialog *dialog = wine_dialog(d->save);
    IShellItem *folder = NULL;
    WCHAR **paths;
    HRESULT hr;
    int n;
    if (!dialog) return E_FAIL;
    IFileDialog_SetOptions(dialog, d->options);
    if (d->title) IFileDialog_SetTitle(dialog, d->title);
    if (d->ok_label) IFileDialog_SetOkButtonLabel(dialog, d->ok_label);
    if (d->nfilters) IFileDialog_SetFileTypes(dialog, d->nfilters, d->filters);
    if (d->filter_index) IFileDialog_SetFileTypeIndex(dialog, d->filter_index);
    if (d->default_ext) IFileDialog_SetDefaultExtension(dialog, d->default_ext);
    if (d->file_name) IFileDialog_SetFileName(dialog, d->file_name);
    if (SUCCEEDED(fd_item_from_path(d->folder ? d->folder : d->default_folder, &folder))) {
        IFileDialog_SetFolder(dialog, folder);
        IShellItem_Release(folder);
    }
    hr = IFileDialog_Show(dialog, owner);
    if (SUCCEEDED(hr)) {
        IFileDialog_GetFileTypeIndex(dialog, &d->filter_index);
        paths = collect_results(dialog, (d->options & FOS_ALLOWMULTISELECT) != 0, &n);
        fd_set_results(d, paths, n);
    }
    IFileDialog_Release(dialog);
    return hr;
}
