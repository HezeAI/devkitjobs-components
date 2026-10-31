// SPDX-License-Identifier: GPL-3.0-or-later
// Static AArch64 syscall launcher, with no private paths. See build.py for ELF emission.
.global _start
_start:
 ldr x4, [sp]
 add x2, sp, #16
 add x2, x2, x4, lsl #3 // envp
 adr x0, sh_path
 adr x5, dash_c
 adr x6, script
 sub sp, sp, #16
 str x0, [sp]
 str x5, [sp, #8]
 str x6, [sp, #16]
 mov x1, sp
 mov x8, #221
 svc #0
 mov x0, #127
 mov x8, #93
 svc #0
// strings sh_path=/system/bin/sh, dash_c=-c; script in build.py.
