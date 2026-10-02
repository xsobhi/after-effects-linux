# mshtml.dll (i386): event handler from an "on<event>" attribute set by setAttribute().
# Source-level description: patches/0008-mshtml-setAttribute-compiles-event-handlers.patch.
#
# HTMLElement_setAttribute, IE9+ branch: the stdcall nsIDOMElement_SetAttribute (call [edx+0xc0])
# is replaced by "call onevent"; its 3 arguments are on the stack, edx is the vtable, and
#   [ebp-0x58] = attribute name (BSTR), [ebp-0x5c] = IHTMLElement (HTMLElement + 0x50),
#   [ebp-0x50] = value VARIANT. Returns the nsresult in eax and pops the arguments (ret 12).
# Position independent (only relative calls): the 32-bit DLL is usually rebased.
        .intel_syntax noprefix
        .text
        .globl onevent
onevent:
        push    dword ptr [esp+0xc]
        push    dword ptr [esp+0xc]
        push    dword ptr [esp+0xc]
        call    dword ptr [edx+0xc0]    # nsIDOMElement_SetAttribute
        push    esi
        push    edi
        push    eax
        sub     esp, 0x50               # 0x18 id, 0x20 VARIANT handler, 0x30 EXCEPINFO
        test    eax, eax
        js      done
        mov     edi, [ebp-0x58]
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
        cmp     word ptr [ebp-0x50], 8  # VT_BSTR value
        jne     done
        mov     esi, [ebp-0x5c]
        sub     esi, 0x50               # HTMLElement (DispatchEx)
        lea     eax, [esp+0x18]         # builtin on<event> property (also on prototypes)?
        mov     [esp], esi
        mov     [esp+4], edi
        mov     dword ptr [esp+8], 8    # fdexNameCaseInsensitive
        mov     [esp+0xc], eax
        call    dispex_get_chain_builtin_id
        test    eax, eax
        js      done
        xor     edi, edi
        mov     dword ptr [esp+0x20], 1 # VT_NULL: an empty value removes the handler
        mov     dword ptr [esp+0x24], 0
        mov     eax, [ebp-0x48]
        test    eax, eax
        jz      put
        cmp     word ptr [eax], 0
        je      put
        mov     ecx, [esi+0x38]         # node.doc
        test    ecx, ecx
        jz      done
        mov     ecx, [ecx+0xd0]         # doc->window
        test    ecx, ecx
        jz      done
        mov     [esp], ecx
        mov     [esp+4], eax
        call    script_parse_event      # same compilation as for attributes in the markup
        test    eax, eax
        jz      done
        mov     edi, eax
        mov     dword ptr [esp+0x20], 9 # VT_DISPATCH
        mov     [esp+0x28], eax
put:
        mov     [esp], esi              # element.on<event> = handler
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
        pop     eax
        pop     edi
        pop     esi
        ret     0xc
