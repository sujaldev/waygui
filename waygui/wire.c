#include "wire.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>

#include "helpers.h"

struct Array {

};

int setup_socket(char *name) {
    int ret;

    const int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0)
        perror("error while creating socket");

    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;

    // Find socket path:
    if (name == NULL)
        name = getenv("WAYLAND_DISPLAY");
    if (name == NULL)
        name = "wayland-0";

    const bool name_is_abs_path = name[0] == '/';
    if (name_is_abs_path) {
        ret = snprintf(addr.sun_path, sizeof addr.sun_path, "%s", name);
    } else {
        char *xdg_runtime_dir = getenv("XDG_RUNTIME_DIR");
        if (xdg_runtime_dir == NULL || xdg_runtime_dir[0] != '/')
            die("error: XDG_RUNTIME_DIR environment variable is either invalid or incorrect.");

        ret = snprintf(addr.sun_path, sizeof addr.sun_path, "%s/%s", xdg_runtime_dir, name);
    }

    if (ret < 0)
        die("error: could not write wayland socket path.");

    if (ret >= sizeof addr.sun_path)
        die("error: wayland socket path was truncated.");


    ret = connect(fd, (const struct sockaddr *) &addr, sizeof(addr));
    if (ret != 0)
        perror("error while connecting socket");

    return fd;
}
