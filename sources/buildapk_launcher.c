#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){
    const char *binary=getenv("DEVKIT_BIN"),*runtime=getenv("DEVKIT_RUNTIME");
    if(!binary||!runtime)return 2;
    char python[4096],script[4096];snprintf(python,sizeof(python),"%s/python3",binary);snprintf(script,sizeof(script),"%s/build-apk.py",runtime);
    char **arguments=calloc(argc+3,sizeof(char *));arguments[0]=python;arguments[1]="-B";arguments[2]=script;
    for(int i=1;i<argc;i++)arguments[i+2]=argv[i];
    execv(python,arguments);return 127;
}
