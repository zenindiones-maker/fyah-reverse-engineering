#!/data/data/com.termux/files/usr/bin/bash
set -eu

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat > "$WORK/probe.s" <<'ASM'
.global _start
.section .text
_start:
    pxor %xmm0, %xmm0
    pcmpeqd %xmm0, %xmm0
    pmovmskb %xmm0, %eax
    cmp $65535, %eax
    jne fail
    lea sse(%rip), %rsi
    mov $sse_end-sse, %edx
    call write_stdout

    vxorps %ymm0, %ymm0, %ymm0
    vmovmskps %ymm0, %eax
    test %eax, %eax
    jne fail
    lea avx(%rip), %rsi
    mov $avx_end-avx, %edx
    call write_stdout

    vpcmpeqd %ymm0, %ymm0, %ymm0
    vpmovmskb %ymm0, %eax
    cmp $-1, %eax
    jne fail
    vzeroupper
    lea avx2(%rip), %rsi
    mov $avx2_end-avx2, %edx
    call write_stdout

    mov $60, %eax
    xor %edi, %edi
    syscall

write_stdout:
    mov $1, %eax
    mov $1, %edi
    syscall
    ret

fail:
    mov $60, %eax
    mov $1, %edi
    syscall

.section .rodata
sse:     .ascii "SSE2_OK\n"
sse_end:
avx:     .ascii "AVX_OK\n"
avx_end:
avx2:    .ascii "AVX2_OK\n"
avx2_end:
ASM

llvm-mc -triple=x86_64-pc-linux-gnu -filetype=obj \
  "$WORK/probe.s" -o "$WORK/probe.o"
ld.lld -m elf_x86_64 -static -e _start \
  "$WORK/probe.o" -o "$WORK/probe"

OUTPUT="$(qemu-x86_64 -cpu max "$WORK/probe")"
printf '%s\n' "$OUTPUT"

for marker in SSE2_OK AVX_OK AVX2_OK; do
  printf '%s\n' "$OUTPUT" | grep -Fxq "$marker" || {
    echo "FAIL: marcador ausente: $marker"
    exit 1
  }
done

echo "PASS: SSE2, AVX e AVX2 executadas pelo QEMU"
