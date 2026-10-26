/* SPDX-License-Identifier: GPL-2.0-only */
/* Pure fixed-profile guards, shared by the driver and native C tests. */
#ifndef A13_MUTED_POLICY_H
#define A13_MUTED_POLICY_H
static inline int a13_profile_ok(unsigned int rate, unsigned int channels,
	unsigned int bits, unsigned long period, unsigned long buffer)
{
	return rate == 48000 && channels == 2 && bits == 16 && period == 1024 &&
		buffer >= 2048 && buffer <= 65536 && buffer % 1024 == 0;
}
static inline int a13_dma_ok(unsigned long long address, unsigned long bytes)
{
	return !(address & 3) && address < (1ULL << 32) && bytes >= 2048 &&
		bytes <= 65536 && !(bytes % 1024) &&
		address + bytes <= (1ULL << 32);
}
/* No caller can enable an ADC, mic bias, analogue output, or clear DAC mute.
 * Values are checked before every physical two-wire write, including cleanup.
 */
static inline int a13_codec_value(unsigned int reg, unsigned int *value)
{
	unsigned int v = *value;
	if (v > 0x1ff)
		return 0;
	switch (reg) {
	case 0x05: v |= 8; break;             /* DACMU always asserted */
	case 0x19: v &= 0x1c0; break;        /* VMID/VREF only; ADC/MIC off */
	case 0x1a: v &= 0x181; break;        /* DACs/PLL only; outputs off */
	case 0x31: v = 0; break;             /* class D outputs hard disabled */
	case 0x2f: v = 0; break;             /* all analogue mixers/PGAs off */
	case 0x02: case 0x03: case 0x28: case 0x29:
	case 0x0a: case 0x0b: v = 0x100; break; /* min volume + update */
	case 0x04: case 0x07: case 0x08: case 0x09: case 0x0f:
	case 0x18: case 0x30: case 0x34: case 0x35: case 0x36: case 0x37:
		break;
	default: return 0;                  /* no arbitrary register access */
	}
	*value = v;
	return 1;
}
#endif
