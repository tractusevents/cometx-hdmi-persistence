"""Verify the supplied evidence and derived artifacts locally; no device access."""
import analyze as a
import hashlib, json, struct

expected = {
    'boot.img': '8648d2e967301b979471b8d7e49ceac47c1774c5d1564b816a419ba0744a34af',
    'running.dtb': '751eebe8733707f68ef8f0a6cce2957239c00a1b999181da7e299f3d9d0cfa41',
    'gsv1127x_upgrade': 'b283c95a8a0bcde8d7ed47d8e89cc6c061433c5f9fd915904c3d01c29eea2e69',
    'gsv2705v1.1.bin': '8899203220fe5b5c8b41464e48ad662834d4ea8ed4ba1b8e2e1e77e0e0995ffc',
}
checks = []
for path,sha in expected.items():
    assert hashlib.sha256((a.ROOT/path).read_bytes()).hexdigest() == sha, path
    checks.append(f'PASS original SHA-256: {path}')

boot = (a.ROOT/'boot.img').read_bytes()
_,nodes = a.fdt(boot)
for name in ('kernel','fdt','resource'):
    props = nodes[f'/images/{name}']
    start = int.from_bytes(props['data-position'],'big')
    size = int.from_bytes(props['data-size'],'big')
    payload = (a.OUT/(name+'.payload')).read_bytes()
    assert payload == boot[start:start+size]
    assert hashlib.sha256(payload).digest() == nodes[f'/images/{name}/hash']['value']
    checks.append(f'PASS FIT {name} payload offset/length/SHA-256')

kernel = (a.OUT/'kernel.raw').read_bytes()
assert kernel[0x38:0x3c] == b'ARMd'
syms = {name:va for va,name,_ in a.symbols()}
assert syms['gsv2705_i2c_switch_channel'] == 0xffffffc008553900
assert syms['channel_store']-syms['gsv2705_i2c_switch_channel'] == 0x70
for i in range(4):
    row = kernel[0xa276a0+12*i:0xa276a0+12*(i+1)]
    assert row[:4] == bytes([0xff,5,i+1,0])
    assert struct.unpack('<II',row[4:]) == (i&1,i>>1)
checks.append('PASS Image magic, switch symbol boundary, and all four routing table entries')

utility = (a.ROOT/'gsv1127x_upgrade').read_bytes()
def crc_table_byte(value):
    for _ in range(8): value = ((value<<1) ^ (7 if value&128 else 0)) & 255
    return value
assert utility[0x29c8:0x2ac8] == bytes(crc_table_byte(i) for i in range(256))
checks.append('PASS all 256 CRC8 table entries match non-reflected polynomial 0x07')

fw = (a.ROOT/'gsv2705v1.1.bin').read_bytes()
assert fw[0x298e0:0x298e8] == fw[0x688e0:0x688e8] == bytes.fromhex('00ffffffffffff00')
assert fw[0x7f000:] == b'\xff'*0x1000
assert max(i for i in range(0x1000,0x40000) if fw[i]!=255) == 0x29907
checks.append('PASS firmware magic locations, application-A extent, and final erased sector')

for path,count in [('offline-hpa-emulation.json',8),('offline-edid-emulation.json',4)]:
    records=json.loads((a.OUT/path).read_text())
    assert len(records)==count
    assert all(r['accesses'] for r in records)
    checks.append(f'PASS saved synthetic trace count: {path} ({count})')

(a.OUT/'verification.txt').write_text('\n'.join(checks)+'\n')
print('\n'.join(checks))
