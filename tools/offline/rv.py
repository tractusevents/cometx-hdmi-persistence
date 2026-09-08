"""RISC-V offline cross-references; comments are local constant propagation hints."""
import analyze as a
import sys, json
from capstone.riscv import RISCV_OP_REG, RISCV_OP_IMM, RISCV_OP_MEM
D=(a.ROOT/'gsv2705v1.1.bin').read_bytes()
BASE=0x20000000
md=a.Cs(a.CS_ARCH_RISCV,a.CS_MODE_RISCV32|a.CS_MODE_RISCVC); md.detail=True; md.skipdata=True

def desc(v):
    if BASE<=v<BASE+len(D):
        b=D[v-BASE:v-BASE+180].split(b'\0')[0]
        if len(b)>3 and all(32<=c<127 or c in (9,10,13) for c in b): return repr(b.decode())
    return ''

def dis(start,end):
    regs={'zero':0,'gp':0x80008860}; lines=[]; refs=[]
    for i in md.disasm(D[start:end],BASE+start):
        m=i.mnemonic; comment=''; o=i.operands if i.id else []
        def reg(k): return i.reg_name(o[k].reg)
        newval=None; dest=None
        if m in ('auipc','lui'):
            dest=reg(0); newval=((i.address if m=='auipc' else 0)+(o[1].imm<<12))&0xffffffff
        elif m in ('addi','ori') and reg(1) in regs:
            dest=reg(0); newval=((regs[reg(1)]+o[2].imm) if m=='addi' else (regs[reg(1)]|o[2].imm))&0xffffffff
        elif m in ('c.addi','c.addi16sp') and reg(0) in regs:
            dest=reg(0); newval=(regs[dest]+o[1].imm)&0xffffffff
        elif m in ('c.li','li'):
            dest=reg(0); newval=o[1].imm&0xffffffff
        elif m=='c.lui':
            dest=reg(0); newval=(o[1].imm<<12)&0xffffffff
        elif m in ('c.mv','mv') and reg(1) in regs:
            dest=reg(0); newval=regs[reg(1)]
        if newval is not None:
            comment=f'{dest}=0x{newval:08x} '+desc(newval)
            refs.append((i.address,newval,'constant'))
        for op in o:
            if op.type==RISCV_OP_MEM:
                r=i.reg_name(op.mem.base)
                if r in regs:
                    v=(regs[r]+op.mem.disp)&0xffffffff
                    comment+=f' MEM[0x{v:08x}]'; refs.append((i.address,v,'memory'))
        if m in ('jal','j','c.j','c.jal','beq','bne','blt','bge','bltu','bgeu','c.beqz','c.bnez','beqz','bnez') and o[-1].type==RISCV_OP_IMM:
            v=(i.address+o[-1].imm)&0xffffffff
            comment+=f' TARGET=0x{v:08x}'; refs.append((i.address,v,'branch'))
        if m=='jalr' and len(o)==3 and reg(1) in regs:
            v=(regs[reg(1)]+o[2].imm)&0xfffffffe
            comment+=f' TARGET=0x{v:08x}'; refs.append((i.address,v,'branch'))
        if m in ('jal','c.jal','jalr'):
            av={r:hex(regs[r]) for r in [f'a{n}' for n in range(5)] if r in regs}
            if av: comment+=' ARGS='+str(av)
        # Drop overwritten registers even when a value cannot be tracked.
        if o and o[0].type==RISCV_OP_REG and m not in ('sw','sb','sh','c.sw','c.swsp','c.sb','c.sh','beq','bne','blt','bge','bltu','bgeu','c.beqz','c.bnez','csrw','csrs','csrc'):
            regs.pop(reg(0),None)
        if dest and newval is not None: regs[dest]=newval
        if m in ('jal','c.jal','jalr'):
            for r in ['ra','t0','t1','t2','t3','t4','t5','t6']+[f'a{n}' for n in range(8)]: regs.pop(r,None)
        if m in ('ret','c.jr','j','c.j','beq','bne','blt','bge','bltu','bgeu','c.beqz','c.bnez'):
            regs={'zero':0,'gp':0x80008860}
        lines.append(f'{i.address:08x}  {i.bytes.hex():8}  {m:12} {i.op_str:30}'+(' ; '+comment if comment else ''))
    return lines,refs

if __name__=='__main__':
    if len(sys.argv)>1:
        s,e=[int(x,16)&0xfffff for x in sys.argv[1:3]]
        print('\n'.join(dis(s,e)[0]))
    else:
        lines,refs=dis(0x1092,0x25fcc)
        (a.OUT/'firmware-A-annotated.asm').write_text('\n'.join(lines))
        (a.OUT/'firmware-A-xrefs.json').write_text(json.dumps(refs))
        print('Instruction lines:',len(lines),'references:',len(refs))
