#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/prctl.h>
#include <unistd.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>

static unsigned long long start_time(pid_t pid) {
    char path[64], buffer[4096];
    snprintf(path, sizeof(path), "/proc/%d/stat", pid);
    FILE *file = fopen(path, "r");
    if (!file) return 0;
    size_t n = fread(buffer, 1, sizeof(buffer)-1, file); fclose(file); buffer[n] = 0;
    char *last = strrchr(buffer, ')');
    if (!last) return 0;
    char *save = NULL, *token = strtok_r(last+2, " ", &save);
    for (int i=0; token && i<19; i++) token = strtok_r(NULL, " ", &save);
    return token ? strtoull(token, NULL, 10) : 0;
}

static int owns_group(pid_t pid, unsigned long long start) {
    char path[64]; struct stat info;
    if (pid <= 1 || start == 0 || start_time(pid) != start) return 0;
    snprintf(path, sizeof(path), "/proc/%d", pid);
    return stat(path, &info) == 0 && info.st_uid == geteuid() &&
           getpgid(pid) == pid && getsid(pid) == pid;
}

int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "--stop") == 0) {
        char *end = NULL; long number = strtol(argv[2], &end, 10);
        if (!end || *end || number <= 1 || number > 2147483647) return 2;
        unsigned long long start = strtoull(argv[3], &end, 10);
        if (!end || *end || !owns_group((pid_t)number, start)) return 3;
        kill(-(pid_t)number, SIGTERM);
        for (int i=0; i<30 && owns_group((pid_t)number, start); i++) usleep(50000);
        if (owns_group((pid_t)number, start)) kill(-(pid_t)number, SIGKILL);
        return 0;
    }
    if (argc < 2) return 2;
    if (setsid() < 0) return 4;
    pid_t parent = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGTERM) < 0) return 5;
    if (getppid() != parent) return 6;
    const char *record = getenv("DEVKIT_PROCESS_RECORD");
    if (record && *record) {
        int fd = open(record, O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW, 0600);
        if (fd < 0) return 7;
        char line[128]; int n = snprintf(line, sizeof(line), "%d %llu\n", getpid(), start_time(getpid()));
        if (write(fd, line, n) != n) { close(fd); return 8; }
        close(fd); unsetenv("DEVKIT_PROCESS_RECORD");
    }
    execv(argv[1], argv+1);
    fprintf(stderr, "DevKitJob's: executable could not start (%d)\n", errno);
    return 127;
}
