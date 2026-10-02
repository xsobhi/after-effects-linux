/* Direct2D text sample: Arial and Verdana at common UI sizes, drawn like D2D apps draw
 * labels (default text antialias mode, system font collection).
 * Build: zig cc -target x86_64-windows-gnu -o d2dtext.exe d2dtext.c -ld2d1 -ldwrite -luser32 */
#define COBJMACROS
#include <windows.h>
#include <initguid.h>
#include <d2d1.h>
#include <dwrite.h>

static ID2D1Factory *d2d;
static IDWriteFactory *dw;
static ID2D1HwndRenderTarget *target;

static void paint(HWND hwnd)
{
    static const WCHAR *faces[] = { L"Arial", L"Verdana" };
    static const float sizes[] = { 11, 12, 13, 14, 16, 20 };
    static const WCHAR text[] = L"Welcome to the FX Console Plug-in Installer 1.0.5";
    ID2D1SolidColorBrush *brush;
    D2D1_COLOR_F bg = { 0.1f, 0.1f, 0.1f, 1 }, fg = { 0.9f, 0.9f, 0.9f, 1 };
    RECT rc;
    float y = 8;
    int f, s;

    if (!target) {
        D2D1_RENDER_TARGET_PROPERTIES props = { 0 };
        D2D1_HWND_RENDER_TARGET_PROPERTIES hprops = { hwnd };
        GetClientRect(hwnd, &rc);
        hprops.pixelSize.width = rc.right;
        hprops.pixelSize.height = rc.bottom;
        ID2D1Factory_CreateHwndRenderTarget(d2d, &props, &hprops, &target);
    }
    ID2D1HwndRenderTarget_BeginDraw(target);
    ID2D1HwndRenderTarget_Clear(target, &bg);
    ID2D1HwndRenderTarget_CreateSolidColorBrush(target, &fg, NULL, &brush);
    for (f = 0; f < 2; f++)
        for (s = 0; s < 6; s++) {
            IDWriteTextFormat *format;
            D2D1_RECT_F box = { 8, y, 800, y + 40 };
            IDWriteFactory_CreateTextFormat(dw, faces[f], NULL, DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL,
                                            DWRITE_FONT_STRETCH_NORMAL, sizes[s], L"en-us", &format);
            ID2D1HwndRenderTarget_DrawText(target, text, ARRAYSIZE(text) - 1, format, &box, (ID2D1Brush *)brush, 0, 0);
            IDWriteTextFormat_Release(format);
            y += sizes[s] + 8;
        }
    ID2D1SolidColorBrush_Release(brush);
    ID2D1HwndRenderTarget_EndDraw(target, NULL, NULL);
    ValidateRect(hwnd, NULL);
}

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_PAINT) { paint(h); return 0; }
    if (msg == WM_DESTROY) PostQuitMessage(0);
    return DefWindowProcW(h, msg, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, LPWSTR cmd, int show)
{
    WNDCLASSW wc = { 0, proc, 0, 0, inst, NULL, LoadCursor(NULL, IDC_ARROW), NULL, NULL, L"d2dtext" };
    MSG msg;
    D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &IID_ID2D1Factory, NULL, (void **)&d2d);
    DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, &IID_IDWriteFactory, (IUnknown **)&dw);
    RegisterClassW(&wc);
    CreateWindowW(L"d2dtext", L"d2dtext", WS_POPUP | WS_VISIBLE, 0, 0, 640, 300, NULL, NULL, inst, NULL);
    while (GetMessageW(&msg, NULL, 0, 0)) DispatchMessageW(&msg);
    return 0;
}
