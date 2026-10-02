#pragma once

// The redesign has no selected electrical configuration. Fill this profile in
// for a specific build; copying an old pin map is not hardware verification.
#ifndef HARDWARE_COMMISSIONED
#define HARDWARE_COMMISSIONED 0
#endif
#ifndef HARDWARE_PROFILE_VERIFIED
#define HARDWARE_PROFILE_VERIFIED 0
#endif

// D2 through D13 for drawers 1 through 4. -1 means unconfigured.
constexpr int LOCK_PINS[4] = {-1, -1, -1, -1};
// Logic level that requests release from the driver. Must be LOW or HIGH.
constexpr int RELEASE_LEVEL = -1;
// Pulse duration and minimum rest AFTER deactivation, in milliseconds.
// Set from the selected lock/driver specifications. Zero is unconfigured.
constexpr unsigned long RELEASE_PULSE_MS = 0;
constexpr unsigned long RELEASE_REST_MS = 0;

// Optional NeoPixel lighting. Leave disabled when absent from the redesign.
constexpr bool LIGHTS_ENABLED = false;
constexpr int LED_DATA_PIN = -1;
constexpr unsigned int LED_COUNT = 0;
constexpr unsigned int PIXEL_START[5] = {0, 0, 0, 0, 0};
constexpr unsigned long LIGHT_TIMEOUT_MS = 30000UL;

// This adapter supports momentary release with an inactive electrical output
// between pulses. Other mechanisms need their own adapter. No sensor or
// mechanical latch behavior is inferred from an acknowledged command.
