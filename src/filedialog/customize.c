/* IFileDialogCustomize: remembers the app's extra controls; show.c maps check boxes and
 * combo/radio lists onto portal "choices" and writes the user's picks back here. */
#include "fd.h"

struct control *fd_control(struct dialog *d, DWORD id)
{
    int i;
    for (i = 0; i < d->ncontrols; i++)
        if (d->controls[i].id == id) return &d->controls[i];
    return NULL;
}

void fd_free_controls(struct dialog *d)
{
    int i, j;
    for (i = 0; i < d->ncontrols; i++) {
        struct control *c = &d->controls[i];
        HeapFree(GetProcessHeap(), 0, c->label);
        HeapFree(GetProcessHeap(), 0, c->group);
        HeapFree(GetProcessHeap(), 0, c->text);
        for (j = 0; j < c->nitems; j++) HeapFree(GetProcessHeap(), 0, c->items[j].label);
    }
    d->ncontrols = 0;
}

static HRESULT add(void *iface, DWORD id, enum ctl_type type, LPCWSTR label, BOOL checked)
{
    struct dialog *d = fd_from_cust(iface);
    struct control *c;
    if (fd_control(d, id)) return E_INVALIDARG;
    if (d->ncontrols >= FD_MAX_CONTROLS) return E_OUTOFMEMORY;
    c = &d->controls[d->ncontrols++];
    memset(c, 0, sizeof(*c));
    c->id = id;
    c->type = type;
    c->label = fd_strdup(label);
    c->group = fd_strdup(d->group);
    c->checked = checked;
    c->state = CDCS_ENABLEDVISIBLE;
    return S_OK;
}

static HRESULT STDMETHODCALLTYPE QueryInterface(void *iface, REFIID riid, void **out)
{ return fd_QueryInterface(&fd_from_cust(iface)->vtbl, riid, out); }
static ULONG STDMETHODCALLTYPE AddRef(void *iface) { return fd_AddRef(&fd_from_cust(iface)->vtbl); }
static ULONG STDMETHODCALLTYPE Release(void *iface) { return fd_Release(&fd_from_cust(iface)->vtbl); }

static HRESULT STDMETHODCALLTYPE EnableOpenDropDown(void *iface, DWORD id) { return add(iface, id, CTL_MENU, NULL, FALSE); }
static HRESULT STDMETHODCALLTYPE AddMenu(void *iface, DWORD id, LPCWSTR l) { return add(iface, id, CTL_MENU, l, FALSE); }
static HRESULT STDMETHODCALLTYPE AddPushButton(void *iface, DWORD id, LPCWSTR l) { return add(iface, id, CTL_BUTTON, l, FALSE); }
static HRESULT STDMETHODCALLTYPE AddComboBox(void *iface, DWORD id) { return add(iface, id, CTL_COMBO, NULL, FALSE); }
static HRESULT STDMETHODCALLTYPE AddRadioButtonList(void *iface, DWORD id) { return add(iface, id, CTL_RADIO, NULL, FALSE); }
static HRESULT STDMETHODCALLTYPE AddCheckButton(void *iface, DWORD id, LPCWSTR l, BOOL c) { return add(iface, id, CTL_CHECK, l, c); }
static HRESULT STDMETHODCALLTYPE AddSeparator(void *iface, DWORD id) { return add(iface, id, CTL_SEPARATOR, NULL, FALSE); }
static HRESULT STDMETHODCALLTYPE AddText(void *iface, DWORD id, LPCWSTR l) { return add(iface, id, CTL_TEXT, l, FALSE); }

static HRESULT STDMETHODCALLTYPE AddEditBox(void *iface, DWORD id, LPCWSTR text)
{
    HRESULT hr = add(iface, id, CTL_EDIT, NULL, FALSE);
    if (SUCCEEDED(hr)) fd_control(fd_from_cust(iface), id)->text = fd_strdup(text);
    return hr;
}

#define CONTROL(var) struct control *var = fd_control(fd_from_cust(iface), id); \
    if (!var) return E_INVALIDARG;

static HRESULT STDMETHODCALLTYPE SetControlLabel(void *iface, DWORD id, LPCWSTR l)
{ CONTROL(c) fd_setstr(&c->label, l); return S_OK; }
static HRESULT STDMETHODCALLTYPE GetControlState(void *iface, DWORD id, CDCONTROLSTATEF *s)
{ CONTROL(c) if (!s) return E_POINTER; *s = c->state; return S_OK; }
static HRESULT STDMETHODCALLTYPE SetControlState(void *iface, DWORD id, CDCONTROLSTATEF s)
{ CONTROL(c) c->state = s; return S_OK; }
static HRESULT STDMETHODCALLTYPE GetEditBoxText(void *iface, DWORD id, WCHAR **t)
{ CONTROL(c) if (!t) return E_POINTER; *t = fd_cotask_strdup(c->text ? c->text : L""); return S_OK; }
static HRESULT STDMETHODCALLTYPE SetEditBoxText(void *iface, DWORD id, LPCWSTR t)
{ CONTROL(c) fd_setstr(&c->text, t); return S_OK; }
static HRESULT STDMETHODCALLTYPE GetCheckButtonState(void *iface, DWORD id, BOOL *b)
{ CONTROL(c) if (!b) return E_POINTER; *b = c->checked; return S_OK; }
static HRESULT STDMETHODCALLTYPE SetCheckButtonState(void *iface, DWORD id, BOOL b)
{ CONTROL(c) c->checked = b; return S_OK; }

static HRESULT STDMETHODCALLTYPE AddControlItem(void *iface, DWORD id, DWORD item, LPCWSTR l)
{
    CONTROL(c)
    if (c->nitems >= FD_MAX_ITEMS) return E_OUTOFMEMORY;
    c->items[c->nitems].id = item;
    c->items[c->nitems++].label = fd_strdup(l ? l : L"");
    if (c->nitems == 1 && c->type == CTL_RADIO) c->selected = item;
    return S_OK;
}

static HRESULT STDMETHODCALLTYPE RemoveControlItem(void *iface, DWORD id, DWORD item)
{
    int i;
    CONTROL(c)
    for (i = 0; i < c->nitems; i++)
        if (c->items[i].id == item) {
            HeapFree(GetProcessHeap(), 0, c->items[i].label);
            memmove(&c->items[i], &c->items[i + 1], (c->nitems - i - 1) * sizeof(c->items[0]));
            c->nitems--;
            return S_OK;
        }
    return E_INVALIDARG;
}

static HRESULT STDMETHODCALLTYPE RemoveAllControlItems(void *iface, DWORD id)
{
    CONTROL(c)
    while (c->nitems) RemoveControlItem(iface, id, c->items[0].id);
    return S_OK;
}

static HRESULT STDMETHODCALLTYPE GetControlItemState(void *iface, DWORD id, DWORD item, CDCONTROLSTATEF *s)
{ CONTROL(c) if (!s) return E_POINTER; *s = CDCS_ENABLEDVISIBLE; return S_OK; }
static HRESULT STDMETHODCALLTYPE SetControlItemState(void *iface, DWORD id, DWORD item, CDCONTROLSTATEF s)
{ CONTROL(c) return S_OK; }
static HRESULT STDMETHODCALLTYPE GetSelectedControlItem(void *iface, DWORD id, DWORD *item)
{ CONTROL(c) if (!item) return E_POINTER; if (!c->nitems) return E_FAIL; *item = c->selected; return S_OK; }
static HRESULT STDMETHODCALLTYPE SetSelectedControlItem(void *iface, DWORD id, DWORD item)
{ CONTROL(c) c->selected = item; return S_OK; }

static HRESULT STDMETHODCALLTYPE SetControlItemText(void *iface, DWORD id, DWORD item, LPCWSTR l)
{
    int i;
    CONTROL(c)
    for (i = 0; i < c->nitems; i++)
        if (c->items[i].id == item) { fd_setstr(&c->items[i].label, l); return S_OK; }
    return E_INVALIDARG;
}

static HRESULT STDMETHODCALLTYPE StartVisualGroup(void *iface, DWORD id, LPCWSTR l)
{
    fd_setstr(&fd_from_cust(iface)->group, l);
    return add(iface, id, CTL_TEXT, l, FALSE);
}

static HRESULT STDMETHODCALLTYPE EndVisualGroup(void *iface)
{ fd_setstr(&fd_from_cust(iface)->group, NULL); return S_OK; }
static HRESULT STDMETHODCALLTYPE MakeProminent(void *iface, DWORD id) { return S_OK; }

static const void *const cust_methods[] = {
    (void *)QueryInterface, (void *)AddRef, (void *)Release, (void *)EnableOpenDropDown,
    (void *)AddMenu, (void *)AddPushButton, (void *)AddComboBox, (void *)AddRadioButtonList,
    (void *)AddCheckButton, (void *)AddEditBox, (void *)AddSeparator, (void *)AddText,
    (void *)SetControlLabel, (void *)GetControlState, (void *)SetControlState,
    (void *)GetEditBoxText, (void *)SetEditBoxText, (void *)GetCheckButtonState,
    (void *)SetCheckButtonState, (void *)AddControlItem, (void *)RemoveControlItem,
    (void *)RemoveAllControlItems, (void *)GetControlItemState, (void *)SetControlItemState,
    (void *)GetSelectedControlItem, (void *)SetSelectedControlItem, (void *)StartVisualGroup,
    (void *)EndVisualGroup, (void *)MakeProminent, (void *)SetControlItemText };
const void *fd_cust_vtbl = cust_methods;
