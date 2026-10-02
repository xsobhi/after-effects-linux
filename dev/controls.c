/* Themed common-controls gallery (comctl32 v6, like installers and plugin dialogs):
 * buttons, check/radio boxes, combo boxes, edits, group box, progress, trackbar, tabs,
 * list view, list box, spin. Screenshot it to compare theme rendering.
 * Build: zig cc -target x86_64-windows-gnu -o controls.exe controls.c controls.rc -lcomctl32 -luser32 -lgdi32 */
#include <windows.h>
#include <commctrl.h>

static HWND add(HWND parent, const WCHAR *cls, const WCHAR *text, DWORD style, int x, int y, int w, int h)
{
    HWND hwnd = CreateWindowExW(0, cls, text, WS_CHILD | WS_VISIBLE | style, x, y, w, h, parent, NULL, NULL, NULL);
    SendMessageW(hwnd, WM_SETFONT, (WPARAM)GetStockObject(DEFAULT_GUI_FONT), TRUE);
    return hwnd;
}

static void fill(HWND parent)
{
    LVCOLUMNW col = { LVCF_TEXT | LVCF_WIDTH, 0, 110, (WCHAR *)L"Name" };
    LVITEMW item = { LVIF_TEXT, 0, 0, 0, 0, (WCHAR *)L"Common Data" };
    TCITEMW tab = { TCIF_TEXT, 0, 0, (WCHAR *)L"General" };
    HWND h;
    int i;

    add(parent, L"BUTTON", L"OK", BS_DEFPUSHBUTTON, 10, 10, 90, 28);
    add(parent, L"BUTTON", L"Cancel", BS_PUSHBUTTON, 110, 10, 90, 28);
    add(parent, L"BUTTON", L"Disabled", BS_PUSHBUTTON | WS_DISABLED, 210, 10, 90, 28);
    h = add(parent, L"BUTTON", L"Checked", BS_AUTOCHECKBOX, 10, 50, 100, 22);
    SendMessageW(h, BM_SETCHECK, BST_CHECKED, 0);
    add(parent, L"BUTTON", L"Unchecked", BS_AUTOCHECKBOX, 110, 50, 100, 22);
    h = add(parent, L"BUTTON", L"Mixed", BS_AUTO3STATE, 210, 50, 80, 22);
    SendMessageW(h, BM_SETCHECK, BST_INDETERMINATE, 0);
    h = add(parent, L"BUTTON", L"Off", BS_AUTOCHECKBOX | WS_DISABLED, 300, 50, 60, 22);
    h = add(parent, L"BUTTON", L"CUDA GPU", BS_AUTORADIOBUTTON | WS_GROUP, 10, 76, 100, 22);
    SendMessageW(h, BM_SETCHECK, BST_CHECKED, 0);
    add(parent, L"BUTTON", L"AMD GPU", BS_AUTORADIOBUTTON, 110, 76, 100, 22);
    add(parent, L"BUTTON", L"Disabled", BS_AUTORADIOBUTTON | WS_DISABLED, 210, 76, 100, 22);
    h = add(parent, L"COMBOBOX", NULL, CBS_DROPDOWNLIST | WS_VSCROLL, 10, 106, 190, 200);
    SendMessageW(h, CB_ADDSTRING, 0, (LPARAM)L"Full installation");
    SendMessageW(h, CB_SETCURSEL, 0, 0);
    h = add(parent, L"COMBOBOX", NULL, CBS_DROPDOWN | WS_VSCROLL, 210, 106, 150, 200);
    SendMessageW(h, CB_ADDSTRING, 0, (LPARAM)L"Editable");
    SendMessageW(h, CB_SETCURSEL, 0, 0);
    add(parent, L"EDIT", L"C:\\Program Files\\Adobe", WS_BORDER | ES_AUTOHSCROLL, 10, 140, 190, 24);
    add(parent, L"EDIT", L"Read only", WS_BORDER | ES_READONLY, 210, 140, 150, 24);
    add(parent, L"BUTTON", L"Group", BS_GROUPBOX, 10, 172, 350, 60);
    h = add(parent, L"msctls_progress32", NULL, 0, 22, 196, 326, 18);
    SendMessageW(h, PBM_SETPOS, 60, 0);
    h = add(parent, L"msctls_trackbar32", NULL, TBS_AUTOTICKS, 10, 240, 200, 30);
    add(parent, L"EDIT", L"5", WS_BORDER | ES_NUMBER, 220, 244, 50, 24);
    h = add(parent, L"msctls_updown32", NULL, UDS_ALIGNRIGHT | UDS_AUTOBUDDY | UDS_SETBUDDYINT, 0, 0, 0, 0);
    h = add(parent, L"SysTabControl32", NULL, 0, 380, 10, 260, 120);
    SendMessageW(h, TCM_INSERTITEMW, 0, (LPARAM)&tab);
    tab.pszText = (WCHAR *)L"Advanced";
    SendMessageW(h, TCM_INSERTITEMW, 1, (LPARAM)&tab);
    h = add(parent, L"SysListView32", NULL, LVS_REPORT | WS_BORDER, 380, 140, 260, 90);
    SendMessageW(h, LVM_INSERTCOLUMNW, 0, (LPARAM)&col);
    col.pszText = (WCHAR *)L"Size";
    SendMessageW(h, LVM_INSERTCOLUMNW, 1, (LPARAM)&col);
    SendMessageW(h, LVM_SETEXTENDEDLISTVIEWSTYLE, 0, LVS_EX_CHECKBOXES | LVS_EX_FULLROWSELECT);
    for (i = 0; i < 6; i++) SendMessageW(h, LVM_INSERTITEMW, 0, (LPARAM)&item);
    h = add(parent, L"LISTBOX", NULL, WS_BORDER | WS_VSCROLL, 380, 240, 260, 60);
    for (i = 0; i < 8; i++) SendMessageW(h, LB_ADDSTRING, 0, (LPARAM)L"AMD GPU");
}

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_DESTROY) PostQuitMessage(0);
    return DefWindowProcW(h, msg, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, LPWSTR cmd, int show)
{
    INITCOMMONCONTROLSEX icc = { sizeof(icc), ICC_WIN95_CLASSES | ICC_STANDARD_CLASSES };
    WNDCLASSW wc = { 0, proc, 0, 0, inst, NULL, LoadCursor(NULL, IDC_ARROW), (HBRUSH)(COLOR_BTNFACE + 1), NULL, L"controls" };
    MSG msg;
    HWND win;

    InitCommonControlsEx(&icc);
    RegisterClassW(&wc);
    win = CreateWindowW(L"controls", L"controls", WS_OVERLAPPEDWINDOW | WS_VISIBLE, 0, 0, 670, 350,
                        NULL, NULL, inst, NULL);
    fill(win);
    while (GetMessageW(&msg, NULL, 0, 0)) {
        if (IsDialogMessageW(win, &msg)) continue;
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return 0;
}
