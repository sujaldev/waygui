#include <stdio.h>
#include <unistd.h>

#include "wire.h"

int main(int argc, char *argv[]) {
    close(setup_socket(NULL));
    return 0;
}
