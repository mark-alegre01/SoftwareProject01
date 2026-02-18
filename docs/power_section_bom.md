# Power Section BOM and Footprint Suggestions

This Bill of Materials (BOM) covers the 12V -> 3.3V power section and the MB102 daughter header/jumper approach for prototyping with ESP32-S3 + RFID.

## Summary
- Input: `J1` DC jack 2.1mm (12V)
- Protection: `F1` polyfuse, `D1` Schottky reverse diode, optional `TVS1`
- Conversion: `U1` Buck converter (12V -> 3.3V), rated >= 2A
- Outputs: `3V3` net to ESP32-S3 and RFID
- MB102: optional daughter header `J_MB102` + `PWR_SEL` jumper to connect MB102 3.3V out to board 3V3

## Suggested parts
- J1: DC barrel jack, 2.1 mm center-positive, through-hole
  - Footprint: `DC_JACK_2.1mm` (KiCad library)
  - Example: CUI Devices PJ-102AH or equivalent

- F1: Resettable polyfuse (PTC)
  - Example: Bourns MF-PSMF250/500 series; choose hold current ~1 A
  - Footprint: small radial PTC or SMD depending on board preference

- D1: Schottky diode (reverse/protection)
  - Example: SS34 (3 A, 40 V, SMC or SMA footprint)
  - Footprint: `DO-214AC (SMA)` or `SMA`/`SMC`

- TVS1 (optional): Transient Voltage Suppressor for 12V line
  - Example: SMBJ12A or SMBJ15A depending on standoff voltage
  - Footprint: SMBJ

- CIN: Input capacitor
  - 100 µF, 25 V electrolytic or polymer (low ESR)
  - Footprint: `CAP-ELEC-6.3x5` or equivalent SMD
  - + 0.1 µF MLCC near VIN pin

- U1: Buck converter (12V -> 3.3V), module or SMD regulator
  - Module (quick): MP1584 adjustable buck module (rated up to 3A) — through-hole header or solder pad footprint for module pins
  - SMD regulator (production): pick a synchronous buck with input rating >= 18 V and 2–3 A capability (check TI, Ricoh, Richtek, etc.)
  - Footprint: depends on chosen regulator — follow datasheet recommended layout for L, C, thermal vias

- COUT: Output capacitor
  - 220–470 µF, 10 V (low ESR), plus 0.1 µF MLCC across output
  - Footprint: electrolytic or polymer radial / SMD

- Decoupling for ESP32-S3 and RFID
  - 100 nF ceramic near each VDD pin
  - 4.7 µF – 10 µF ceramic per VDD supply rail near module

- MB102 header
  - Header: 1x4 or 2x3 depending on MB102 pinout
  - Example mapping (1x4): VIN, 5V_OUT, 3V3_OUT, GND
  - Footprint: through-hole male header (0.1" pitch)

- PWR_SEL jumper
  - 2-pin jumper, 0.1" pitch (to connect MB102 3V3_OUT to main 3V3 when desired)

- Testpoints
  - `TP_VIN`, `TP_3V3`, `TP_GND` — small testpoint pads or looped pads

## Example footprints in KiCad
- `DC_JACK_2.1mm` — on KiCad library
- `SS34` — `D_SMA` footprint
- `PAD_MP1584` — if using module: create 4-pin pad area for VIN, GND, VOUT, EN (if present)
- `CAP_221_MLCC` / `CAP_ELEC_1210` for caps
- `HDR_1x2` for `PWR_SEL`

## Notes
- When you select an SMD buck IC, follow its reference layout exactly (inductor, input/output caps close to pins) and add thermal vias on the ground pad.
- If you use an MP1584 module for easier prototyping, solder it onto pads or headers and verify the output voltage before connecting the ESP32/RFID.

## Quick test procedure
1. Build only the input side and the buck module (no ESP32 or RFID connected).
2. With a multimeter, connect 12V power to `J1` and measure `TP_3V3` — adjust buck (if adjustable) to read 3.30 V.
3. Verify `TP_GND` continuity and proper polarity.
4. Connect ESP32 & RFID and observe boot; verify Wi‑Fi functions and RFID reads.

---

If you want, I can also create a KiCad `.sch` with standard symbols (DC_JACK, D_SCHOTTKY, FUSE, BUCK module symbol, header, jumper). I kept the BOM generic so you can choose exact footprints.
