# mshtml.dll (i386): "on<event>" attributes set or removed by script also set or clear the
# element's event handler, as in IE9+. Source-level description:
# patches/0009-mshtml-setAttribute-compiles-event-handlers.patch. Placed after the end of .text
# by build.py. Position independent (only relative calls): the 32-bit DLL is usually rebased.
        .intel_syntax noprefix
        .text

# HTMLElement_setAttribute, IE9+ branch: replaces the stdcall "call [edx+0xc0]"
# (nsIDOMElement_SetAttribute, 3 arguments on the stack, edx = vtable).
# [ebp-0x58] = name, [ebp-0x5c] = IHTMLElement (HTMLElement + 0x50), [ebp-0x50] = value VARIANT.
        .globl set_hook
set_hook:
        push    dword ptr [esp+0xc]
        push    dword ptr [esp+0xc]
        push    dword ptr [esp+0xc]
        call    dword ptr [edx+0xc0]
        test    eax, eax
        js      1f
        cmp     word ptr [ebp-0x50], 8  # VT_BSTR
        jne     1f
        push    eax
        push    dword ptr [ebp-0x48]
        push    dword ptr [ebp-0x58]
        mov     ecx, [ebp-0x5c]
        sub     ecx, 0x50
        push    ecx
        call    set_handler
        add     esp, 0xc
        pop     eax
1:      ret     0xc

# HTMLElement_removeAttribute, IE9+ branch, the attribute exists: replaces the stdcall
# "call [edx+0xc8]" (nsIDOMElement_RemoveAttribute, 2 arguments).
# [ebp+0x8] = IHTMLElement, [ebp+0xc] = name.
        .globl remove_hook
remove_hook:
        push    dword ptr [esp+0x8]
        push    dword ptr [esp+0x8]
        call    dword ptr [edx+0xc8]
        test    eax, eax
        js      1f
        push    eax
        push    0
        push    dword ptr [ebp+0xc]
        mov     ecx, [ebp+0x8]
        sub     ecx, 0x50
        push    ecx
        call    set_handler
        add     esp, 0xc
        pop     eax
1:      ret     0x8

# set_handler(HTMLElement *elem, const WCHAR *name, const WCHAR *text), cdecl: if name is one
# of the element's builtin on<event> properties, elem.on<event> = function compiled from text
# (like attributes in the markup), or null for a NULL/empty text.
        .globl set_handler
set_handler:
        push    esi
        push    edi
        push    ebx
        sub     esp, 0x50               # 0x18 id, 0x20 VARIANT handler, 0x30 EXCEPINFO
        mov     esi, [esp+0x60]
        mov     edi, [esp+0x64]
        mov     ebx, [esp+0x68]
        test    edi, edi
        jz      done
        movzx   eax, word ptr [edi]     # name starts with "on" (any case)?
        or      eax, 0x20
        cmp     eax, 'o'
        jne     done
        movzx   eax, word ptr [edi+2]
        or      eax, 0x20
        cmp     eax, 'n'
        jne     done
        lea     eax, [esp+0x18]         # builtin property, also found on prototypes
        mov     [esp], esi
        mov     [esp+4], edi
        mov     dword ptr [esp+8], 8    # fdexNameCaseInsensitive
        mov     [esp+0xc], eax
        call    dispex_get_chain_builtin_id
        test    eax, eax
        js      done
        xor     edi, edi
        mov     dword ptr [esp+0x20], 1 # VT_NULL
        mov     dword ptr [esp+0x24], 0
        test    ebx, ebx
        jz      put
        cmp     word ptr [ebx], 0
        je      put
        mov     ecx, [esi+0x38]         # node.doc
        test    ecx, ecx
        jz      done
        mov     ecx, [ecx+0xd0]         # doc->window
        test    ecx, ecx
        jz      done
        mov     [esp], ecx
        mov     [esp+4], ebx
        call    script_parse_event
        test    eax, eax
        jz      done
        mov     edi, eax
        mov     dword ptr [esp+0x20], 9 # VT_DISPATCH
        mov     [esp+0x28], eax
put:
        mov     [esp], esi
        mov     eax, [esp+0x18]
        mov     [esp+4], eax
        mov     dword ptr [esp+8], 0x800        # LOCALE_SYSTEM_DEFAULT
        lea     eax, [esp+0x20]
        mov     [esp+0xc], eax
        lea     eax, [esp+0x30]
        mov     [esp+0x10], eax
        mov     dword ptr [esp+0x14], 0
        call    dispex_prop_put
        test    edi, edi
        jz      done
        mov     eax, [edi]
        push    edi
        call    dword ptr [eax+8]       # IDispatch_Release
done:
        add     esp, 0x50
        pop     ebx
        pop     edi
        pop     esi
        ret
