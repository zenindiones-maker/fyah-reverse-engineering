#!/data/data/com.termux/files/usr/bin/bash
set -eu

QEMU="${QEMU:-qemu-x86_64}"
WORK="$(mktemp -d "${TMPDIR:-$HOME}/ps5-elf-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

for tool in llvm-mc ld.lld readelf grep; do
    command -v "$tool" >/dev/null 2>&1 ||
        fail "ferramenta ausente: $tool"
done

command -v "$QEMU" >/dev/null 2>&1 ||
    fail "QEMU indisponível: $QEMU"

cat > "$WORK/probe.s" <<'ASM'
.global _start
.section .text
_start:
    # uname(struct utsname *) — Linux x86-64 syscall 63
    mov $63, %rax
    lea uts(%rip), %rdi
    syscall
    test %rax, %rax
    jne fail

    # utsname.machine começa no offset 260: "x86_64"
    cmpl $0x5f363878, uts+260(%rip)
    jne fail
    cmpw $0x3436, uts+264(%rip)
    jne fail

    # getpid() — syscall 39
    mov $39, %rax
    syscall
    test %rax, %rax
    jle fail

    # Mensagem esperada
    mov $1, %rax
    mov $1, %rdi
    lea success(%rip), %rsi
    mov $success_end-success, %rdx
    syscall

    mov $60, %rax
    xor %rdi, %rdi
    syscall

fail:
    mov $60, %rax
    mov $1, %rdi
    syscall

.section .rodata
success:
    .ascii "GUEST_UNAME_X86_64_AND_GETPID_OK\n"
success_end:

.section .bss
.balign 8
uts:
    .skip 390
ASM

llvm-mc -triple=x86_64-pc-linux-gnu \
    -filetype=obj "$WORK/probe.s" -o "$WORK/probe.o" ||
    fail "montagem falhou"

ld.lld -m elf_x86_64 -static -e _start \
    "$WORK/probe.o" -o "$WORK/probe" ||
    fail "linkedição falhou"

HEADER="$(readelf -h "$WORK/probe")" ||
    fail "não foi possível ler o cabeçalho ELF"

printf '%s\n' "$HEADER" | grep -q 'Class:.*ELF64' ||
    fail "o ELF não é ELF64"

printf '%s\n' "$HEADER" | grep -q 'Machine:.*X86-64' ||
    fail "o ELF não é x86-64"

printf '%s\n' 'ELF_ARCHITECTURE_OK'

if OUTPUT="$("$QEMU" "$WORK/probe" 2>&1)"; then
    :
else
    RC=$?
    printf '%s\n' "$OUTPUT" >&2
    fail "QEMU terminou com código $RC"
fi

printf '%s\n' "$OUTPUT" | grep -Fxq \
    'GUEST_UNAME_X86_64_AND_GETPID_OK' ||
    fail "saída esperada ausente"

printf '%s\n' "$OUTPUT"
printf '%s\n' 'PASS: ELF, arquitetura, execução e saída verificados'
