"""Offline CPU harness, synthetic RAM/MMIO only. No hardware or network APIs.

Not a chip emulator: external devices are inert memory. Results prove CPU paths
for explicit synthetic inputs, never electrical behavior or real timing.
"""
import analyze as a
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.riscv_const import *
import json, struct
D=(a.ROOT/'gsv2705v1.1.bin').read_bytes()
class Harness:
    def __init__(self):
        self.u=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        self.u.mem_map(0x20000000,0x80000); self.u.mem_write(0x20000000,D)
        self.u.mem_map(0x80000000,0x100000)
        self.u.mem_map(0x30020000,0x10000)
        self.u.mem_write(0x80000000,D[0x259cc:0x25da0])
        self.u.mem_write(0x80008000,D[0x29878:0x29908])
        self.w32(0x800080e4,0x200011f6); self.w32(0x800080e8,0x20001294)
        self.access=[]; self.logs=[]
        self.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,self.mem,begin=0x30020000,end=0x3002ffff)
        self.u.hook_add(UC_HOOK_CODE,self.log,begin=0x2001cc70,end=0x2001cc70)
    def w32(self,addr,v): self.u.mem_write(addr,struct.pack('<I',v))
    def r32(self,addr): return struct.unpack('<I',self.u.mem_read(addr,4))[0]
    def mem(self,u,typ,addr,size,val,_):
        self.access.append({'pc':hex(u.reg_read(UC_RISCV_REG_PC)),'access':'write' if typ==17 else 'read','register':hex(addr-0x30020000),'size':size,'value':hex(val) if typ==17 else bytes(u.mem_read(addr,size)).hex()})
    def log(self,u,addr,size,_):
        p=u.reg_read(UC_RISCV_REG_A0)
        s=bytes(u.mem_read(p,180)).split(b'\0')[0].decode(errors='replace')
        self.logs.append([s,u.reg_read(UC_RISCV_REG_A1),u.reg_read(UC_RISCV_REG_A2)])
        u.reg_write(UC_RISCV_REG_PC,u.reg_read(UC_RISCV_REG_RA))
    def port(self,portid=1):
        p=0x80010000
        self.w32(p,0x80013000)
        self.w32(p+8,portid)
        for o,n in [(0x1c,0x80011000),(0x20,0x80011100),(0x24,0x80011200),(0x28,0x80011300),(0x2c,0x80011400),(0x30,0x80011500)]: self.w32(p+o,n)
        return p
    def call(self,off,*args):
        self.u.reg_write(UC_RISCV_REG_SP,0x800ff000)
        self.u.reg_write(UC_RISCV_REG_GP,0x80008860)
        self.u.reg_write(UC_RISCV_REG_RA,0x2007fffc)
        for n,arg in enumerate(args): self.u.reg_write(UC_RISCV_REG_A0+n,arg)
        self.u.emu_start(0x20000000+off,0x2007fffc,count=100000)
        pc=self.u.reg_read(UC_RISCV_REG_PC)
        if pc!=0x2007fffc: raise RuntimeError(f'Instruction budget exhausted at {pc:x}')
        return self.u.reg_read(UC_RISCV_REG_A0)

if __name__=='__main__':
    results=[]
    for portid in range(4):
        for off,name in [(0x15f3e,'disable_hpa'),(0x16236,'enable_hpa')]:
            h=Harness(); p=h.port(portid)
            initial = {0xbb:0xa1, 0xb2:0xb1, 0xb5:0xc1, 0xb6:0xd1, 0x2674:0x81}
            for reg,value in initial.items(): h.u.mem_write(0x30020000+reg,bytes([value]))
            h.call(off,p)
            low = (1 & ~(1 << portid)) if off == 0x15f3e else (1 | (1 << portid))
            for reg in (0xbb,0xb2,0xb5,0xb6):
                assert h.u.mem_read(0x30020000+reg,1)[0] == (initial[reg]&0xf0)|low
            expected = (0x81 & ~(1 << portid)) if off == 0x15f3e else (0x81 | (1 << portid))
            assert h.u.mem_read(0x30022674,1)[0] == expected
            results.append({'function':hex(0x20000000+off),'name':name,'synthetic_portid':portid,'initial_registers':{hex(k):hex(v) for k,v in initial.items()},'accesses':h.access,'logs':h.logs})
    (a.OUT/'offline-hpa-emulation.json').write_text(json.dumps(results,indent=2))
    print(f'PASS: {len(results)} synthetic HPA paths, per-port bit masks and upper-nibble preservation.')
    edid_results=[]
    for portid,porttype,length in [(1,0,256),(1,0,512),(3,0,512),(1,1,512)]:
        h=Harness(); p=h.port(portid); h.w32(p+4,porttype)
        source=0x80014000
        pattern=bytes((i ^ (i>>8))&255 for i in range(512))
        h.u.mem_write(source,pattern)
        h.call(0x19ef8,p,source,length)
        writes=[x for x in h.access if x['access']=='write']
        expected=[(0x267a,porttype),(0x267a,porttype)]
        expected += [(0x1000+i,pattern[i]) for i in range(256)]
        if length>256:
            expected += [(0x267a,0x10|porttype)]
            expected += [(0x1000+i,pattern[256+i]) for i in range(256)]
        assert [(int(x['register'],16),int(x['value'],16)) for x in writes] == expected
        edid_results.append({'function':'0x20019ef8','synthetic_portid':portid,'synthetic_porttype':porttype,'length':length,'accesses':h.access,'logs':h.logs})
    (a.OUT/'offline-edid-emulation.json').write_text(json.dumps(edid_results,indent=2))
    print(f'PASS: {len(edid_results)} synthetic EDID paths, bank selection and exact write order/content.')
