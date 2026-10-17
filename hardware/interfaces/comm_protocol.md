# Host-MCU Communication Protocol (v1)

Status: PROVISIONAL until CP3. All hardware in the demo is SIMULATED. Proof-of-concept prototype, not a medical device.

## 1. Link
- USB-CDC serial (PROVISIONAL).
- Nominal baud: 115200 (PROVISIONAL; USB-CDC ignores it physically, set for host tools).
- Byte order: little-endian.

## 2. Frame format (both directions)
| Field | Size | Meaning |
|---|---|---|
| SOF | 1 byte | Start marker 0xA5 |
| TYPE | 1 byte | 0x01 command, 0x02 status |
| LEN | 1 byte | Payload length in bytes (CRC not included) |
| PAYLOAD | LEN bytes | See sections 3 and 4 |
| CRC16 | 2 bytes | Over TYPE, LEN and PAYLOAD |

CRC: CRC-16/CCITT-FALSE (polynomial 0x1021, init 0xFFFF, no reflection, no final XOR). Design choice, PROVISIONAL.

## 3. Command (host to MCU, every 1 s)
| Field | Type | Meaning |
|---|---|---|
| seq | uint16 | Sequence number |
| heat_pct[4] | uint8 x 4 | Heat_1..4, 0 to 100 (%) |
| master_enable | uint8 | 1 = master switch may close, 0 = open |

LEN = 7. Total frame = 12 bytes.
A frame with any heat_pct above 100 is treated as invalid and dropped.

## 4. Status (MCU to host, every hw_status_period_s = 1 s)
| Field | Type | Meaning |
|---|---|---|
| seq | uint16 | Sequence number |
| t_ms | uint32 | MCU time in ms |
| module_temp[4][2] | int16 x 8 | 0.01 degC; 0x7FFF = invalid (NaN). Order: ch1 A, ch1 B, ch2 A ... ch4 B |
| heater_current[4] | uint16 x 4 | mA; 0xFFFF = invalid (NaN) |
| connected_bits | uint8 | Bit (i-1) = 1 if channel i connected |
| hw_cutoff_bits | uint8 | Bit (i-1) = 1 if channel i hardware cutoff tripped |
| hw_fault_code | uint16 | System fault code, see fault_codes.csv; 0 = none |
| fw_state | uint8 | Firmware state (enumeration TBD) |

LEN = 33. Total frame = 38 bytes.

## 5. Error handling
- A frame with a bad CRC, wrong LEN or wrong SOF is dropped and counted.
- Too many bad frames in a window raises system fault 6 (COMM_CRC_ERROR_RATE). Window length and threshold: TBD.
- No valid command frame within host_heartbeat_timeout_s: MCU switches all heaters OFF (system fault 1). Value: at least 2 command periods, PROVISIONAL.
- No valid status frame within data_stale_hw_s: the host raises system fault 8.

## 6. Open items (TBD)
- fw_state enumeration.
- CRC error window and threshold.
- Final baud and framing (CP3).
