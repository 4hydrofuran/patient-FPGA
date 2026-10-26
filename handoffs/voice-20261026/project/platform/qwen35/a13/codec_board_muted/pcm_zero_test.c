// SPDX-License-Identifier: GPL-2.0-only
/* Root maintenance test: ZERO data only, exact hw: device. No capture/file IO. */
#include <alsa/asoundlib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void require(int ret, const char *name)
{
	if (ret < 0) {
		fprintf(stderr, "A13_PCM_FAILURE %s: %s\n", name, snd_strerror(ret));
		exit(2); /* normal process exit/ALSA close, never a signal/retry */
	}
}
static double monotonic(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec + t.tv_nsec / 1e9;
}
int main(int argc, char **argv)
{
	snd_pcm_t *pcm;
	snd_pcm_hw_params_t *hw;
	snd_pcm_sw_params_t *sw;
	short zeros[512] = {0};
	snd_pcm_uframes_t frames, written = 0;
	int ret, drop, rejected = 0;
	double start, elapsed;
	if (argc != 3 || strncmp(argv[1], "hw:", 3) ||
	    (strcmp(argv[2], "drain") && strcmp(argv[2], "drop")))
		return 64;
	drop = !strcmp(argv[2], "drop");
	frames = drop ? 16384 : 49152;
	require(snd_pcm_open(&pcm, argv[1], SND_PCM_STREAM_PLAYBACK, 0), "open");
	snd_pcm_hw_params_alloca(&hw);
	snd_pcm_sw_params_alloca(&sw);
	require(snd_pcm_hw_params_any(pcm, hw), "negative rate baseline");
	if (snd_pcm_hw_params_set_rate(pcm, hw, 16000, 0) < 0) rejected++;
	require(snd_pcm_hw_params_any(pcm, hw), "negative format baseline");
	if (snd_pcm_hw_params_set_format(pcm, hw, SND_PCM_FORMAT_S24_LE) < 0) rejected++;
	require(snd_pcm_hw_params_any(pcm, hw), "negative channels baseline");
	if (snd_pcm_hw_params_set_channels(pcm, hw, 1) < 0) rejected++;
	require(snd_pcm_hw_params_any(pcm, hw), "negative mmap baseline");
	if (snd_pcm_hw_params_set_access(pcm, hw, SND_PCM_ACCESS_MMAP_INTERLEAVED) < 0) rejected++;
	if (rejected != 4) {
		fprintf(stderr, "A13_PCM_FAILURE expected four strict constraint rejections, got %d\n", rejected);
		snd_pcm_close(pcm); return 3;
	}
	require(snd_pcm_hw_params_any(pcm, hw), "params any");
	require(snd_pcm_hw_params_set_access(pcm, hw, SND_PCM_ACCESS_RW_INTERLEAVED), "access");
	require(snd_pcm_hw_params_set_format(pcm, hw, SND_PCM_FORMAT_S16_LE), "format");
	require(snd_pcm_hw_params_set_rate(pcm, hw, 48000, 0), "rate");
	require(snd_pcm_hw_params_set_channels(pcm, hw, 2), "channels");
	require(snd_pcm_hw_params_set_period_size(pcm, hw, 256, 0), "period");
	require(snd_pcm_hw_params_set_buffer_size(pcm, hw, 2048), "buffer");
	require(snd_pcm_hw_params(pcm, hw), "hw_params");
	require(snd_pcm_sw_params_current(pcm, sw), "sw_params current");
	require(snd_pcm_sw_params_set_start_threshold(pcm, sw, 2048), "start threshold");
	require(snd_pcm_sw_params_set_avail_min(pcm, sw, 256), "avail_min");
	require(snd_pcm_sw_params(pcm, sw), "sw_params");
	require(snd_pcm_prepare(pcm), "prepare");
	printf("{\"event\":\"PREPARED_MUTED_ZERO_ONLY\",\"constraint_rejections\":%d}\n", rejected); fflush(stdout);
	start = monotonic();
	while (written < frames) {
		snd_pcm_sframes_t n = snd_pcm_writei(pcm, zeros, 256);
		if (n <= 0) { require(n < 0 ? (int)n : -EIO, "writei no recovery"); }
		written += n;
	}
	ret = drop ? snd_pcm_drop(pcm) : snd_pcm_drain(pcm);
	require(ret, drop ? "drop" : "drain");
	elapsed = monotonic() - start;
	require(snd_pcm_hw_free(pcm), "hw_free");
	require(snd_pcm_close(pcm), "close");
	printf("{\"event\":\"MUTED_PCM_CLOSED\",\"zero_frames_written\":%lu,\"stop_mode\":\"%s\",\"elapsed_seconds\":%.9f,\"recording\":false,\"audible_test\":false}\n",
		(unsigned long)written, argv[2], elapsed);
	return 0;
}
