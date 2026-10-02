/* DirectWrite font check: lists the families of the system font collection and looks up
 * a few names, as text-layout code does. Prints to stdout.
 * Build: zig cc -target x86_64-windows-gnu -o dwfonts.exe dwfonts.c -ldwrite -lole32 */
#define COBJMACROS
#include <windows.h>
#include <initguid.h>
#include <dwrite.h>
#include <stdio.h>

int main(void)
{
    static const WCHAR *names[] = { L"Tahoma", L"Arial", L"arial", L"Verdana", L"Segoe UI", L"Ubuntu" };
    IDWriteFactory *factory;
    IDWriteFontCollection *coll;
    UINT32 count, i, index;
    BOOL exists;
    HRESULT hr;

    hr = DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, &IID_IDWriteFactory, (IUnknown **)&factory);
    if (FAILED(hr)) { printf("DWriteCreateFactory %#lx\n", hr); return 1; }
    hr = IDWriteFactory_GetSystemFontCollection(factory, &coll, FALSE);
    if (FAILED(hr)) { printf("GetSystemFontCollection %#lx\n", hr); return 1; }
    count = IDWriteFontCollection_GetFontFamilyCount(coll);
    printf("families: %u\n", count);
    for (i = 0; i < count && i < 400; i++) {
        IDWriteFontFamily *family;
        IDWriteLocalizedStrings *strings;
        WCHAR name[128] = L"?";
        if (SUCCEEDED(IDWriteFontCollection_GetFontFamily(coll, i, &family))) {
            if (SUCCEEDED(IDWriteFontFamily_GetFamilyNames(family, &strings))) {
                IDWriteLocalizedStrings_GetString(strings, 0, name, ARRAYSIZE(name));
                IDWriteLocalizedStrings_Release(strings);
            }
            printf("  %ls (%u fonts)\n", name, IDWriteFontFamily_GetFontCount(family));
            IDWriteFontFamily_Release(family);
        }
    }
    for (i = 0; i < ARRAYSIZE(names); i++) {
        exists = FALSE;
        hr = IDWriteFontCollection_FindFamilyName(coll, names[i], &index, &exists);
        printf("FindFamilyName %ls: hr %#lx exists %d\n", names[i], hr, exists);
    }
    return 0;
}
