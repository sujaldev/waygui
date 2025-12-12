#include "waygui.h"

#include <stdio.h>
#include <stdint.h>
#include <sys/socket.h>
#include <unistd.h>

#include "helpers.h"
#include "wire.h"

/* This corresponds to wl_display::get_registry(new_id)
 * wl_display is implicitly assumed to have an object ID of 1.
 */
struct wl_display_msg {
    uint32_t obj_id;
    uint32_t opcode;
    uint32_t new_id;
};

void update_size(struct wl_display_msg *msg) {
    msg->opcode = ((uint32_t) sizeof (*msg) << (2 * 8)) | msg->opcode;
}

void create_window() {
    ssize_t ret;
    int fd = setup_socket(NULL);

    struct wl_display_msg msg = {
        .obj_id = 0x01,
        .opcode = 0x01,
        .new_id = 0x02,
    };

    update_size(&msg);

    ret = send(fd, &msg, sizeof (msg), 0);

    if (ret < 0)
        perror("error while sending wire message");

    if (ret != sizeof(msg))
        die("error: unable to send entire message");

    char recv_data[4096] = {0};
    ret = recv(fd, &recv_data, sizeof recv_data, 0);

    if (ret < 0)
        perror("error while receiving data from wayland server");

    close(fd);
}
