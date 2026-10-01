/* COM server entry points for filedialog.dll. */
#include "fd.h"

LONG fd_objects;
static LONG locks;

HRESULT fd_create(BOOL save, REFIID riid, void **out)
{
    struct dialog *d = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(*d));
    HRESULT hr;
    if (!d) return E_OUTOFMEMORY;
    d->vtbl = save ? fd_save_vtbl : fd_open_vtbl;
    d->cust_vtbl = fd_cust_vtbl;
    d->ref = 1;
    d->save = save;
    d->options = save ? (FOS_OVERWRITEPROMPT | FOS_NOREADONLYRETURN | FOS_PATHMUSTEXIST)
                      : (FOS_PATHMUSTEXIST | FOS_FILEMUSTEXIST);
    InterlockedIncrement(&fd_objects);
    hr = fd_QueryInterface(&d->vtbl, riid, out);
    fd_Release(&d->vtbl);
    return hr;
}

struct factory { const void *vtbl; BOOL save; };

static HRESULT STDMETHODCALLTYPE cf_QueryInterface(void *iface, REFIID riid, void **out)
{
    if (!out) return E_POINTER;
    if (IsEqualIID(riid, &IID_IUnknown) || IsEqualIID(riid, &IID_IClassFactory)) {
        *out = iface;
        return S_OK;
    }
    *out = NULL;
    return E_NOINTERFACE;
}

static ULONG STDMETHODCALLTYPE cf_AddRef(void *iface) { return 2; }
static ULONG STDMETHODCALLTYPE cf_Release(void *iface) { return 1; }

static HRESULT STDMETHODCALLTYPE cf_CreateInstance(void *iface, IUnknown *outer, REFIID riid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (outer) return CLASS_E_NOAGGREGATION;
    return fd_create(((struct factory *)iface)->save, riid, out);
}

static HRESULT STDMETHODCALLTYPE cf_LockServer(void *iface, BOOL lock)
{
    if (lock) InterlockedIncrement(&locks);
    else InterlockedDecrement(&locks);
    return S_OK;
}

static const void *const factory_methods[] = {
    (void *)cf_QueryInterface, (void *)cf_AddRef, (void *)cf_Release,
    (void *)cf_CreateInstance, (void *)cf_LockServer };
static struct factory open_factory = { factory_methods, FALSE };
static struct factory save_factory = { factory_methods, TRUE };

HRESULT WINAPI DllGetClassObject(REFCLSID clsid, REFIID riid, void **out)
{
    struct factory *f;
    if (IsEqualCLSID(clsid, &CLSID_FileOpenDialog)) f = &open_factory;
    else if (IsEqualCLSID(clsid, &CLSID_FileSaveDialog)) f = &save_factory;
    else return CLASS_E_CLASSNOTAVAILABLE;
    return cf_QueryInterface(f, riid, out);
}

HRESULT WINAPI DllCanUnloadNow(void)
{
    return (fd_objects || locks) ? S_FALSE : S_OK;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, void *reserved)
{
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(instance);
    return TRUE;
}
