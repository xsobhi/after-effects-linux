# mshtml.dll (x86_64): event handler from an "on<event>" attribute set by setAttribute().
# Source-level description: patches/0008-mshtml-setAttribute-compiles-event-handlers.patch.
#
# HTMLElement_setAttribute, IE9+ branch: the call nsIDOMElement_SetAttribute (call [rax+0x180])
# is replaced by "call onevent". On entry rcx/rdx/r8/rax are still set up for that call and
#   rbx = attribute name (BSTR), r14 = HTMLElement (its DispatchEx), [rbp-0x20] = value VARIANT.
# Returns the nsresult in eax, like the replaced call. Built by build.sh at the end of .text.
        .intel_syntax noprefix
        .text
        .globl onevent
onevent:
        push    rsi
        push    rdi
        sub     rsp, 0x98               # 0x30 id, 0x38 VARIANT handler, 0x50 EXCEPINFO
        call    qword ptr [rax+0x180]   # nsIDOMElement_SetAttribute
        mov     esi, eax
        test    eax, eax
        js      done
        test    rbx, rbx
        jz      done
        movzx   eax, word ptr [rbx]     # name starts with "on" (any case)?
        or      eax, 0x20
        cmp     eax, 'o'
        jne     done
        movzx   eax, word ptr [rbx+2]
        or      eax, 0x20
        cmp     eax, 'n'
        jne     done
        cmp     word ptr [rbp-0x20], 8  # VT_BSTR value
        jne     done
        mov     rcx, r14                # builtin on<event> property (also on prototypes)?
        mov     rdx, rbx
        mov     r8d, 8                  # fdexNameCaseInsensitive
        lea     r9, [rsp+0x30]
        call    dispex_get_chain_builtin_id
        test    eax, eax
        js      done
        xor     edi, edi
        mov     qword ptr [rsp+0x38], 1 # VT_NULL: an empty value removes the handler
        mov     rdx, [rbp-0x18]
        test    rdx, rdx
        jz      put
        cmp     word ptr [rdx], 0
        je      put
        mov     rcx, [r14+0x70]         # node.doc
        test    rcx, rcx
        jz      done
        mov     rcx, [rcx+0x1a0]        # doc->window
        test    rcx, rcx
        jz      done
        call    script_parse_event      # same compilation as for attributes in the markup
        test    rax, rax
        jz      done
        mov     rdi, rax
        mov     qword ptr [rsp+0x38], 9 # VT_DISPATCH
        mov     [rsp+0x40], rax
put:
        mov     rcx, r14                # element.on<event> = handler
        mov     edx, [rsp+0x30]
        mov     r8d, 0x800              # LOCALE_SYSTEM_DEFAULT
        lea     r9, [rsp+0x38]
        lea     rax, [rsp+0x50]
        mov     [rsp+0x20], rax
        mov     qword ptr [rsp+0x28], 0
        call    dispex_prop_put
        test    rdi, rdi
        jz      done
        mov     rcx, rdi
        mov     rax, [rdi]
        call    qword ptr [rax+0x10]    # IDispatch_Release
done:
        mov     eax, esi
        add     rsp, 0x98
        pop     rdi
        pop     rsi
        ret
