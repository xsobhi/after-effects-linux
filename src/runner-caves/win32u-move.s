# win32u move_window_bits (moving a child window within its parent's window surface):
# copy only the part of the old window rectangle that was visible in the parent and
# invalidate the rest of the destination. Wine copied the whole rectangle, so pixels of
# whatever lay outside the parent (e.g. After Effects' timeline below a scrolled panel
# stack) showed in the panel until the app happened to repaint it; wineserver's exposure
# (new minus old visible region, without the move offset) never invalidates that area.
# Placed at 0x1bd870 in the Proton-CachyOS 11.0 x86_64 win32u.so (lib/wine_caves.py),
# flush_cave at +0x1b0. Assembled with as --64; calls resolved with nm to the internal
# functions, NtGetTickCount = its PLT entry 0x2f700, back = 0x4f434, flush_back = 0x4dea6,
# move_time = 0x2ae750 (just past .bss).
# Rects (parent client coords): dst ebx/r15d/[rbp-0x50]/[rbp-0x54],
# src r12d/r14d/[rbp-0x58]/[rbp-0x4c]; hwnd [rbp-0x48]; r13 = struct window_rects *.
        .intel_syntax noprefix
        .text
cave:
        sub     rsp, 0x40                       # [rsp] clip box, +0x10 parent, +0x18 dc,
        mov     rdi, [rbp-0x48]                 # +0x20 old dst, +0x30/+0x38 regions
        mov     esi, 1                          # GA_PARENT
        call    NtUserGetAncestor
        test    rax, rax
        je      out
        mov     [rsp+0x10], rax
        call    get_desktop_window
        cmp     rax, [rsp+0x10]
        je      out                             # top-level window: nothing to clip to
        mov     rdi, [rsp+0x10]
        xor     esi, esi
        mov     edx, 2                          # DCX_CACHE: the parent's visible region
        call    NtUserGetDCEx
        test    rax, rax
        je      out
        mov     [rsp+0x18], rax
        mov     rdi, rax
        mov     rsi, rsp
        call    NtGdiGetAppClipBox
        mov     [rsp+0x30], eax
        mov     rdi, [rsp+0x10]
        mov     rsi, [rsp+0x18]
        call    NtUserReleaseDC
        cmp     dword ptr [rsp+0x30], 0         # ERROR
        je      out
        mov     [rsp+0x20], ebx                 # keep the full destination
        mov     [rsp+0x24], r15d
        mov     eax, [rbp-0x50]
        mov     [rsp+0x28], eax
        mov     eax, [rbp-0x54]
        mov     [rsp+0x2c], eax
        mov     eax, ebx
        sub     eax, r12d                       # dx
        mov     ecx, r15d
        sub     ecx, r14d                       # dy
        cmp     r12d, [rsp]
        cmovl   r12d, [rsp]                     # src &= clip box
        cmp     r14d, [rsp+4]
        cmovl   r14d, [rsp+4]
        mov     edx, [rbp-0x58]
        cmp     edx, [rsp+8]
        cmovg   edx, [rsp+8]
        mov     esi, [rbp-0x4c]
        cmp     esi, [rsp+0xc]
        cmovg   esi, [rsp+0xc]
        cmp     edx, r12d
        cmovl   edx, r12d
        cmp     esi, r14d
        cmovl   esi, r14d
        mov     [rbp-0x58], edx
        mov     [rbp-0x4c], esi
        lea     ebx, [r12+rax]                  # dst = src + (dx, dy)
        lea     r15d, [r14+rcx]
        lea     edi, [rdx+rax]
        mov     [rbp-0x50], edi
        lea     edi, [rsi+rcx]
        mov     [rbp-0x54], edi
        cmp     ebx, [rsp+0x20]                 # whole destination copied: done
        jne     invalidate
        cmp     r15d, [rsp+0x24]
        jne     invalidate
        cmp     edi, [rsp+0x2c]
        jne     invalidate
        mov     eax, [rbp-0x50]
        cmp     eax, [rsp+0x28]
        je      out
invalidate:                                     # region = full dst - copied dst
        mov     edi, [rsp+0x20]
        mov     esi, [rsp+0x24]
        mov     edx, [rsp+0x28]
        mov     ecx, [rsp+0x2c]
        call    NtGdiCreateRectRgn
        mov     [rsp+0x30], rax
        mov     edi, ebx
        mov     esi, r15d
        mov     edx, [rbp-0x50]
        mov     ecx, [rbp-0x54]
        call    NtGdiCreateRectRgn
        mov     [rsp+0x38], rax
        mov     rdi, [rsp+0x30]
        mov     rsi, rdi
        mov     rdx, rax
        mov     ecx, 4                          # RGN_DIFF
        call    NtGdiCombineRgn
        mov     rdi, [rsp+0x30]                 # parent client -> window client coords
        mov     esi, [r13+0x10]
        neg     esi
        mov     edx, [r13+0x14]
        neg     edx
        call    NtGdiOffsetRgn
        mov     rdi, [rbp-0x48]
        xor     esi, esi
        mov     rdx, [rsp+0x30]
        mov     ecx, 0x485                      # RDW_INVALIDATE|ERASE|ALLCHILDREN|FRAME
        call    NtUserRedrawWindow
        call    NtGetTickCount                  # let the app repaint before the next idle
        or      eax, 1                          # flush shows the window (flush_cave)
        mov     dword ptr [rip+move_time], eax
        mov     rdi, [rsp+0x30]
        call    NtGdiDeleteObjectApp
        mov     rdi, [rsp+0x38]
        call    NtGdiDeleteObjectApp
out:
        add     rsp, 0x40
        mov     rdi, [rbp-0x48]                 # the two instructions replaced by the jump
        lea     rsi, [rbp-0x34]
        jmp     back

# flush_window_surfaces( BOOL idle ): skip idle flushes for 40 ms after move_window_bits
# invalidated a moved window, so the pending WM_PAINT lands before the frame is shown.
flush_cave:
        test    edi, edi
        je      flush
        mov     eax, dword ptr [rip+move_time]
        test    eax, eax
        je      flush
        push    rdi
        call    NtGetTickCount
        pop     rdi
        sub     eax, dword ptr [rip+move_time]
        cmp     eax, 40
        jb      skip
        mov     dword ptr [rip+move_time], 0
flush:
        push    rbp                             # the instructions replaced by the jump
        mov     rbp, rsp
        push    r13
        jmp     flush_back
skip:
        ret
