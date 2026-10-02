# mshtml.dll (x86_64): "on<event>" attributes set or removed by script also set or clear the
# element's event handler, as in IE9+. Source-level description:
# patches/0009-mshtml-setAttribute-compiles-event-handlers.patch. Placed after the end of .text
# by build.py; every entry point gets an unwind entry (UNWIND in build.py matches the prologs).
        .intel_syntax noprefix
        .text

# HTMLElement_setAttribute, IE9+ branch: replaces "call [rax+0x180]" (nsIDOMElement_SetAttribute;
# rcx/rdx/r8/rax are set up for it). rbx = name, r14 = HTMLElement, [rbp-0x20] = value VARIANT.
        .globl set_hook
set_hook:
        sub     rsp, 0x28
        call    qword ptr [rax+0x180]
        test    eax, eax
        js      1f
        cmp     word ptr [rbp-0x20], 8  # VT_BSTR
        jne     1f
        mov     [rsp+0x20], eax
        mov     rcx, r14
        mov     rdx, rbx
        mov     r8, [rbp-0x18]
        call    set_handler
        mov     eax, [rsp+0x20]
1:      add     rsp, 0x28
        ret

# HTMLElement_removeAttribute, IE9+ branch, the attribute exists: replaces "call [rax+0x190]"
# (nsIDOMElement_RemoveAttribute). rbx = name, r14 = HTMLElement.
        .globl remove_hook
remove_hook:
        sub     rsp, 0x28
        call    qword ptr [rax+0x190]
        test    eax, eax
        js      1f
        mov     [rsp+0x20], eax
        mov     rcx, r14
        mov     rdx, rbx
        xor     r8d, r8d
        call    set_handler
        mov     eax, [rsp+0x20]
1:      add     rsp, 0x28
        ret

# set_handler(HTMLElement *elem, const WCHAR *name, const WCHAR *text): if name is one of the
# element's builtin on<event> properties, elem.on<event> = function compiled from text
# (like attributes in the markup), or null for a NULL/empty text.
        .globl set_handler
set_handler:
        push    rsi
        push    rdi
        push    rbx
        sub     rsp, 0x90               # 0x30 id, 0x38 VARIANT handler, 0x50 EXCEPINFO
        mov     rsi, rcx
        mov     rdi, rdx
        mov     rbx, r8
        test    rdi, rdi
        jz      done
        movzx   eax, word ptr [rdi]     # name starts with "on" (any case)?
        or      eax, 0x20
        cmp     eax, 'o'
        jne     done
        movzx   eax, word ptr [rdi+2]
        or      eax, 0x20
        cmp     eax, 'n'
        jne     done
        mov     rcx, rsi                # builtin property, also found on prototypes
        mov     rdx, rdi
        mov     r8d, 8                  # fdexNameCaseInsensitive
        lea     r9, [rsp+0x30]
        call    dispex_get_chain_builtin_id
        test    eax, eax
        js      done
        xor     edi, edi
        mov     qword ptr [rsp+0x38], 1 # VT_NULL
        test    rbx, rbx
        jz      put
        cmp     word ptr [rbx], 0
        je      put
        mov     rcx, [rsi+0x70]         # node.doc
        test    rcx, rcx
        jz      done
        mov     rcx, [rcx+0x1a0]        # doc->window
        test    rcx, rcx
        jz      done
        mov     rdx, rbx
        call    script_parse_event
        test    rax, rax
        jz      done
        mov     rdi, rax
        mov     qword ptr [rsp+0x38], 9 # VT_DISPATCH
        mov     [rsp+0x40], rax
put:
        mov     rcx, rsi
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
        add     rsp, 0x90
        pop     rbx
        pop     rdi
        pop     rsi
        ret
