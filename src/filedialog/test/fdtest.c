/* Exercise CLSID_FileOpenDialog / CLSID_FileSaveDialog the way Adobe apps do. */
#define COBJMACROS
#define CINTERFACE
#include <windows.h>
#include <shobjidl.h>
#include <stdio.h>

int main(int argc, char **argv)
{
    BOOL save = argc > 1 && !strcmp(argv[1], "save");
    COMDLG_FILTERSPEC types[] = { { L"All Footage Files", L"*.png;*.mov;*.mp4" }, { L"All Files", L"*.*" } };
    IFileDialog *dialog = NULL;
    IFileDialogCustomize *custom = NULL;
    IShellItem *item = NULL;
    WCHAR *path = NULL;
    BOOL checked = FALSE;
    DWORD selected = 0;
    UINT type = 0;
    HRESULT hr;
    CoInitialize(NULL);
    hr = CoCreateInstance(save ? &CLSID_FileSaveDialog : &CLSID_FileOpenDialog, NULL, CLSCTX_INPROC_SERVER,
                          &IID_IFileDialog, (void **)&dialog);
    printf("create %08lx\n", hr);
    if (FAILED(hr)) return 1;
    IFileDialog_SetTitle(dialog, save ? L"Save As" : L"Import File");
    IFileDialog_SetFileTypes(dialog, 2, types);
    if (save) IFileDialog_SetFileName(dialog, L"Untitled Project");
    if (SUCCEEDED(IFileDialog_QueryInterface(dialog, &IID_IFileDialogCustomize, (void **)&custom))) {
        IFileDialogCustomize_AddCheckButton(custom, 100, L"PNG Sequence", FALSE);
        IFileDialogCustomize_StartVisualGroup(custom, 200, L"Import As:");
        IFileDialogCustomize_AddComboBox(custom, 201);
        IFileDialogCustomize_AddControlItem(custom, 201, 1, L"Footage");
        IFileDialogCustomize_AddControlItem(custom, 201, 2, L"Composition");
        IFileDialogCustomize_SetSelectedControlItem(custom, 201, 2);
        IFileDialogCustomize_EndVisualGroup(custom);
    }
    hr = IFileDialog_Show(dialog, NULL);
    printf("show %08lx\n", hr);
    if (SUCCEEDED(hr) && SUCCEEDED(IFileDialog_GetResult(dialog, &item))) {
        IShellItem_GetDisplayName(item, SIGDN_FILESYSPATH, &path);
        printf("result %ls\n", path);
    }
    IFileDialog_GetFileTypeIndex(dialog, &type);
    if (custom) {
        IFileDialogCustomize_GetCheckButtonState(custom, 100, &checked);
        IFileDialogCustomize_GetSelectedControlItem(custom, 201, &selected);
    }
    printf("type %u checked %d importas %lu\n", type, checked, selected);
    return 0;
}
