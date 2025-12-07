#ifndef WAYGUI_HELPERS_H
#define WAYGUI_HELPERS_H

/** Visibility attribute */
#if defined(__GNUC__) && __GNUC__ >= 4
#define WG_EXPORT __attribute__ ((visibility("default")))
#else
#define WG_EXPORT
#endif


void die(const char *fmt, ...);

#endif //WAYGUI_HELPERS_H
