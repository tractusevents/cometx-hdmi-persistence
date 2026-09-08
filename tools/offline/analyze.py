"""Offline-only extraction/disassembly. Never opens a device or network connection."""
import sys, struct, json, hashlib, re, bisect, collections, math, zlib, gzip, lzma
from pathlib import Path
import os
PROJECT = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get('COMETX_INPUTS', PROJECT/'inputs')).resolve()
OUT = Path(os.environ.get('COMETX_OUTPUT', PROJECT/'output')).resolve()
OUT.mkdir(parents=True, exist_ok=True)
from capstone import *
from elftools.elf.elffile import ELFFile

def fdt(data):
    magic, size, soff, stroff, *_ = struct.unpack_from('>10I', data)
    assert magic == 0xd00dfeed
    p, stack, nodes = soff, [], {}
    while True:
        t = struct.unpack_from('>I', data, p)[0]; p += 4
        if t == 1:
            e = data.index(0, p); stack.append(data[p:e].decode()); p = (e+4)&~3
            nodes['/'.join(stack)] = {}
        elif t == 2: stack.pop()
        elif t == 3:
            n, so = struct.unpack_from('>II', data, p); p += 8
            key = data[stroff+so:data.index(0, stroff+so)].decode()
            nodes['/'.join(stack)][key] = data[p:p+n]; p = (p+n+3)&~3
        elif t == 4: pass
        elif t == 9: break
        else: raise ValueError((p,t))
    return size, nodes

def fmt_prop(b):
    if b and b[-1] == 0 and all(c in (0,9,10,13) or 32 <= c < 127 for c in b):
        return repr(b.rstrip(b'\0').decode())
    return b.hex(' ')

def extract():
    boot = (ROOT/'boot.img').read_bytes()
    size, nodes = fdt(boot)
    lines = [f'FIT header size: 0x{size:x}']
    for path, props in nodes.items():
        lines.append(path)
        lines += [f'  {k}: {fmt_prop(v)}' for k,v in props.items()]
        if path.startswith('/images/') and 'data-size' in props:
            n = int.from_bytes(props['data-size'],'big')
            if 'data-position' in props: off = int.from_bytes(props['data-position'],'big')
            else: off = size + int.from_bytes(props['data-offset'],'big')
            d = boot[off:off+n]
            name = path.split('/')[-1]
            (OUT/(name+'.payload')).write_bytes(d)
            lines.append(f'  EXTRACTED boot offset 0x{off:x}, size 0x{n:x}, sha256 {hashlib.sha256(d).hexdigest()}')
            if props.get('compression',b'') == b'lz4\0':
                import lz4.frame, lz4.block
                if d[:4] == bytes.fromhex('02214c18'):
                    p, blocks = 4, []
                    while p+4 <= len(d):
                        bs = struct.unpack_from('<I', d, p)[0]; p += 4
                        if not bs: break
                        blocks.append(lz4.block.decompress(d[p:p+bs],uncompressed_size=8*1024*1024)); p += bs
                    raw = b''.join(blocks)
                else: raw = lz4.frame.decompress(d)
            elif props.get('compression',b'') == b'gzip\0': raw = gzip.decompress(d)
            else: raw = d
            (OUT/(name+'.raw')).write_bytes(raw)
            lines.append(f'  DECOMPRESSED size 0x{len(raw):x}, sha256 {hashlib.sha256(raw).hexdigest()}, first64 {raw[:64].hex()}')
    (OUT/'boot-layout.txt').write_text('\n'.join(lines))
    _, dt = fdt((ROOT/'running.dtb').read_bytes())
    (OUT/'device-tree.txt').write_text('\n'.join(path+'\n'+'\n'.join(f'  {k}: {fmt_prop(v)}' for k,v in ps.items()) for path,ps in dt.items()))
    print('\n'.join(lines))

def symbols():
    syms = []
    for line in (ROOT/'kallsyms.txt').read_text().splitlines():
        s = line.split()
        if len(s)>=3: syms.append((int(s[0],16),s[2],s[1]))
    return sorted(syms)

def strings(data, minimum=5):
    return [(m.start(),m.group().decode()) for m in re.finditer(rb'[\x20-\x7e]{%d,}'%minimum,data)]

def arm64_comment(ins, regs, desc):
    """Conservative straight-line address hints; never evidence by themselves."""
    ops = ins.operands
    previous = dict(regs)
    def name(reg):
        s = ins.reg_name(reg)
        return 'x'+s[1:] if s.startswith('w') else s
    for reg in ins.regs_access()[1]:
        regs.pop(name(reg), None)
    comment = ''
    if ins.mnemonic in ('adr', 'adrp'):
        val = ops[1].imm & ((1 << 64)-1)
        regs[name(ops[0].reg)] = val
        comment = desc(val)
    elif ins.mnemonic == 'add' and len(ops) == 3 and ops[2].type == 2:
        source = name(ops[1].reg)
        if source in previous:
            val = (previous[source] + (ops[2].imm << ops[2].shift.value)) & ((1 << 64)-1)
            regs[name(ops[0].reg)] = val
            comment = desc(val)
    if ins.mnemonic in ('bl', 'b') and ops and ops[0].type == 2:
        comment = desc(ops[0].imm)
    if any(ins.group(g) for g in (CS_GRP_JUMP, CS_GRP_CALL, CS_GRP_RET)):
        regs.clear()
    return comment

def kernel():
    d = (OUT/'kernel.raw').read_bytes()
    syms = symbols(); addrs = [s[0] for s in syms]
    base = 0xffffffc008000000
    md = Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN); md.detail = True
    targets = [(a,n,t) for a,n,t in syms if 0xffffffc008552a00 <= a < 0xffffffc008555300]
    labels = {a:n for a,n,t in syms}
    def desc(addr):
        addr &= (1<<64)-1
        if addr in labels: return labels[addr]
        if 0 <= addr-base < len(d):
            b = d[addr-base:addr-base+160].split(b'\0')[0]
            if len(b)>2 and all(32<=c<127 or c in (9,10,13) for c in b): return repr(b.decode())
        i = bisect.bisect_right(addrs,addr)-1
        return f'{syms[i][1]}+0x{addr-syms[i][0]:x}' if i>=0 else ''
    lines = [f'Image base VA = 0x{base:x}; file offset = VA - base.']
    for a,n,t in targets:
        i = bisect.bisect_right(addrs,a); end = addrs[i]
        lines.append(f'\n{n}: VA 0x{a:x}, Image offset 0x{a-base:x}, length 0x{end-a:x}')
        regs = {}
        for ins in md.disasm(d[a-base:end-base], a):
            comment = arm64_comment(ins, regs, desc)
            lines.append(f'{ins.address:016x}  {ins.bytes.hex():8}  {ins.mnemonic:8} {ins.op_str:44}'+(f' ; {comment}' if comment else ''))
    (OUT/'kernel-driver.asm').write_text('\n'.join(lines))
    print('\n'.join(f'{a:x} {n}' for a,n,t in targets))
    print('Image magic',d[0x38:0x3c], 'Linux version',next((s for o,s in strings(d) if s.startswith('Linux version ')),None))

def utility():
    path = ROOT/'gsv1127x_upgrade'; d=path.read_bytes()
    elf=ELFFile(path.open('rb'))
    labels={}; summary=[]
    for sec in elf.iter_sections():
        summary.append(f'{sec.name:20} VA 0x{sec["sh_addr"]:x} off 0x{sec["sh_offset"]:x} size 0x{sec["sh_size"]:x}')
        if sec['sh_type'] in ('SHT_SYMTAB','SHT_DYNSYM'):
            for sym in sec.iter_symbols():
                if sym['st_value']: labels[sym['st_value']]=sym.name
                summary.append(f'  SYM {sym.name} value=0x{sym["st_value"]:x} size=0x{sym["st_size"]:x}')
    rela=elf.get_section_by_name('.rela.plt'); dyn=elf.get_section_by_name('.dynsym'); plt=elf.get_section_by_name('.plt')
    if rela:
        for i,rel in enumerate(rela.iter_relocations()): labels[plt['sh_addr']+32+i*16] = dyn.get_symbol(rel['r_info_sym']).name+'@plt'
    summary.append('\nFunction ranges from .eh_frame FDEs:')
    for entry in elf.get_dwarf_info().EH_CFI_entries():
        if 'initial_location' in getattr(entry, 'header', {}):
            summary.append(f"  FDE VA 0x{entry['initial_location']:x} size 0x{entry['address_range']:x}")
    def desc(addr):
        if addr in labels: return labels[addr]
        for sec in elf.iter_sections():
            if sec['sh_addr']<=addr<sec['sh_addr']+sec['sh_size'] and sec['sh_type']!='SHT_NOBITS':
                b=sec.data()[addr-sec['sh_addr']:addr-sec['sh_addr']+200].split(b'\0')[0]
                if len(b)>1 and all(32<=c<127 or c in (9,10,13) for c in b): return repr(b.decode())
        return ''
    md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN); md.detail=True
    lines=[]
    for sec in elf.iter_sections():
        if not sec['sh_flags']&4: continue
        regs={}
        for ins in md.disasm(sec.data(),sec['sh_addr']):
            if ins.address in labels: lines.append('\n'+labels[ins.address]+':')
            comment = arm64_comment(ins, regs, desc)
            lines.append(f'{ins.address:08x}  {ins.bytes.hex():8}  {ins.mnemonic:8} {ins.op_str:42}'+(f' ; {comment}' if comment else ''))
    (OUT/'upgrade-elf.txt').write_text('\n'.join(summary))
    (OUT/'upgrade.asm').write_text('\n'.join(lines))
    (OUT/'upgrade-strings.txt').write_text('\n'.join(f'{o:08x} {s}' for o,s in strings(d)))
    print('\n'.join(summary))

def firmware():
    d=(ROOT/'gsv2705v1.1.bin').read_bytes()
    (OUT/'firmware-strings.txt').write_text('\n'.join(f'{o:08x} {s}' for o,s in strings(d)))
    md=Cs(CS_ARCH_RISCV,CS_MODE_RISCV32|CS_MODE_RISCVC); md.skipdata=True
    lines=[]
    for ins in md.disasm(d,0x20000000):
        lines.append(f'{ins.address:08x}  {ins.bytes.hex():8}  {ins.mnemonic:12} {ins.op_str}')
    (OUT/'firmware-rv32.asm').write_text('\n'.join(lines))
    stats=[]
    for o in range(0,len(d),4096):
        b=d[o:o+4096]; c=collections.Counter(b)
        h=-sum(n/len(b)*math.log2(n/len(b)) for n in c.values())
        stats.append(f'{o:06x} entropy={h:.3f} zero={c[0]:4} ff={c[255]:4}')
    (OUT/'firmware-entropy.txt').write_text('\n'.join(stats))
    print('\n'.join(f'{o:08x} {s}' for o,s in strings(d) if re.search(r'edid|hpd|ddc|switch|mail|2705|version|rx[a-d]|KVM',s,re.I)))

if __name__=='__main__':
    tasks = {'extract': extract, 'kernel': kernel, 'utility': utility, 'firmware': firmware}
    for task in sys.argv[1:]:
        if task not in tasks: raise SystemExit('Choose extract, kernel, utility, firmware')
        tasks[task]()
