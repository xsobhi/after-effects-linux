/* GDI+ smoothing test: draws the shapes After Effects' UI uses (rounded buttons, radio
 * circles, curves, text) with SmoothingModeAntiAlias, to compare Wine's and Microsoft's GDI+.
 * Build: zig cc -target x86_64-windows-gnu -o gdiptest.exe gdiptest.c -lgdiplus -luser32 -lgdi32 */
#include <windows.h>
#include <gdiplus.h>
#include <stdio.h>

static FILE *out;
#define CHECK(call) do { GpStatus st_ = call; if (out) fprintf(out, "%s -> %d\n", #call, st_); } while (0)

static void paint(HDC dc)
{
    GpGraphics *g;
    GpPen *pen;
    GpPath *path;
    GpSolidFill *brush, *text;
    GpFontFamily *family;
    GpFont *font;
    RectF box = { 20, 200, 400, 40 };
    int i;

    GdipCreateFromHDC(dc, &g);
    GdipSetSmoothingMode(g, SmoothingModeAntiAlias);
    GdipCreateSolidFill(0xff232323, &brush);
    GdipFillRectangleI(g, brush, 0, 0, 480, 300);
    GdipCreatePen1(0xffe0e0e0, 1.5f, UnitPixel, &pen);

    GdipCreatePath(FillModeAlternate, &path);           /* rounded "OK" button */
    GdipAddPathArc(path, 20, 20, 24, 24, 180, 90);
    GdipAddPathArc(path, 116, 20, 24, 24, 270, 90);
    GdipAddPathArc(path, 116, 36, 24, 24, 0, 90);
    GdipAddPathArc(path, 20, 36, 24, 24, 90, 90);
    GdipClosePathFigure(path);
    GdipDrawPath(g, pen, path);

    GdipCreateSolidFill(0xffe0e0e0, &text);
    for (i = 0; i < 3; i++)                              /* radio buttons */
        GdipDrawEllipse(g, pen, 170 + i * 30, 26, 14, 14);
    GdipFillEllipse(g, (GpBrush *)text, 174, 30, 6, 6);

    GdipDrawBezier(g, pen, 20, 180, 120, 60, 260, 60, 440, 170);   /* graph editor curve */

    {
        static const WCHAR *names[] = { L"Arial", L"Verdana", L"Tahoma", L"Ubuntu", L"Noto Sans", L"Marlett" };
        GpFontFamily *f;
        for (i = 0; i < 6; i++)
            if (out) { GpStatus st = GdipCreateFontFamilyFromName(names[i], NULL, &f); fprintf(out, "family %ls -> %d\n", names[i], st); if (!st) GdipDeleteFontFamily(f); }
    }
    CHECK(GdipCreateFontFamilyFromName(L"Arial", NULL, &family));
    CHECK(GdipCreateFont(family, 12, FontStyleRegular, UnitPixel, &font));
    CHECK(GdipSetTextRenderingHint(g, TextRenderingHintAntiAliasGridFit));
    CHECK(GdipDrawString(g, L"Composition  Layer  Effect  0;00;00;00", -1, font, &box, NULL, (GpBrush *)text));
    if (out) fflush(out);

    GdipDeleteFont(font); GdipDeleteFontFamily(family); GdipDeleteBrush((GpBrush *)text);
    GdipDeletePath(path); GdipDeletePen(pen); GdipDeleteBrush((GpBrush *)brush);
    GdipDeleteGraphics(g);
}

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_PAINT) { PAINTSTRUCT ps; paint(BeginPaint(h, &ps)); EndPaint(h, &ps); return 0; }
    if (msg == WM_DESTROY) PostQuitMessage(0);
    return DefWindowProcW(h, msg, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, LPWSTR cmd, int show)
{
    GdiplusStartupInput in = { 1, NULL, FALSE, FALSE };
    ULONG_PTR token;
    WNDCLASSW wc = { 0, proc, 0, 0, inst, NULL, LoadCursor(NULL, IDC_ARROW), NULL, NULL, L"gdiptest" };
    MSG msg;
    out = fopen("gdiptest.log", "w");
    GdiplusStartup(&token, &in, NULL);
    RegisterClassW(&wc);
    CreateWindowW(L"gdiptest", cmd && *cmd ? cmd : L"gdiptest", WS_OVERLAPPEDWINDOW | WS_VISIBLE,
                  0, 0, 500, 340, NULL, NULL, inst, NULL);
    while (GetMessageW(&msg, NULL, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    GdiplusShutdown(token);
    return 0;
}
