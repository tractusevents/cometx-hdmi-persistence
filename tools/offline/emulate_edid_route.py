"""Trace the EDID bank assignment routine with explicit synthetic MMIO values."""
from emulate_rv import Harness
import analyze as a
import json
cases=[]
for pid in range(4):
    for typ in (0,1):
        h=Harness(); p=h.port(pid); h.w32(p+4,typ)
        initial={0x2677:0xa1,0x267d:0xa5,0x2674:0x80}
        for reg,value in initial.items(): h.u.mem_write(0x30020000+reg,bytes([value]))
        h.call(0x1a596,p)
        bit=1<<pid
        expected=[(0x2677,0xa5),(0x267d,(0xa5&~bit)|(typ<<pid)),(0x2674,0x80|bit)]
        writes=[(int(x['register'],16),int(x['value'],16)) for x in h.access if x['access']=='write']
        assert writes==expected,(pid,typ,writes,expected)
        cases.append(dict(port_id=pid,port_type=typ,initial={hex(k):hex(v) for k,v in initial.items()},accesses=h.access))
(a.OUT/'offline-edid-route-emulation.json').write_text(json.dumps(cases,indent=2)+'\n')
print('PASS: 8 synthetic paths: 2677 bit 2 enabled, 267d per-input RAM bank selected, 2674 per-input bit enabled.')
