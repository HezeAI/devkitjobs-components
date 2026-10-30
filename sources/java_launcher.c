#include <jni.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

/* Android HotSpot uses dladdr's library filename to derive java.home before
 * parsing -Djava.home. Adapt only libjvm's filename query; code stays in the
 * read-only APK native directory, data in the app's Java runtime directory. */
__attribute__((visibility("default"))) int dkaddr(const void *address,Dl_info *info) {
    int result=dladdr(address,info);
    const char *home=getenv("JAVA_HOME");
    static __thread char logical[PATH_MAX];
    if(result&&home&&info->dli_fname&&strstr(info->dli_fname,"libjvm.so")) {
        if(snprintf(logical,sizeof(logical),"%s/lib/server/libjvm.so",home)>=(int)sizeof(logical))return 0;
        info->dli_fname=logical;
    }
    return result;
}

typedef jint (*create_vm)(JavaVM **,void **,void *);
static char *option(const char *key,const char *value) {
    size_t size=strlen(key)+strlen(value)+2;char *result=malloc(size);
    if(result)snprintf(result,size,"%s%s",key,value);return result;
}
int main(int argc,char **argv) {
    const char *library=getenv("DEVKIT_LIBDIR"),*home=getenv("JAVA_HOME"),*runtime=getenv("DEVKIT_RUNTIME");
    if(!library||!home||!runtime){fprintf(stderr,"DevKitJob's Java runtime is not configured\n");return 2;}
    char path[4096];snprintf(path,sizeof(path),"%s/libjvm.so",library);
    void *handle=dlopen(path,RTLD_NOW|RTLD_GLOBAL);
    if(!handle){fprintf(stderr,"Cannot load app-owned Java VM: %s\n",dlerror());return 3;}
    create_vm create=(create_vm)dlsym(handle,"JNI_CreateJavaVM");if(!create)return 4;
    JavaVMOption *options=calloc(argc+20,sizeof(JavaVMOption));int count=0;
    options[count++].optionString=option("-Djava.home=",home);
    options[count++].optionString=option("-Djava.library.path=",library);
    options[count++].optionString=option("-Dsun.boot.library.path=",library);
    snprintf(path,sizeof(path),"%s/launcher.jar",runtime);
    options[count++].optionString=option("-Djava.class.path=",path);
    options[count++].optionString=option("-Djava.io.tmpdir=",getenv("TMPDIR")?getenv("TMPDIR"):home);
    options[count++].optionString=option("-Duser.home=",getenv("HOME")?getenv("HOME"):home);
    options[count++].optionString="-Djdk.lang.Process.launchMechanism=FORK";
    options[count++].optionString="-Dfile.encoding=UTF-8";
    options[count++].optionString="-Xmx1024m";
    options[count++].optionString="--add-exports=java.base/sun.security.tools.keytool=ALL-UNNAMED";
    options[count++].optionString="-Dorg.gradle.native=false";
    options[count++].optionString="-Dorg.gradle.vfs.watch=false";
    options[count++].optionString="-Dorg.gradle.internal.instrumentation.agent=false";
    for(int i=1;i<argc;i++) {
        if(!strcmp(argv[i],"-cp")||!strcmp(argv[i],"-classpath")||!strcmp(argv[i],"--class-path")){i++;continue;}
        if(!strncmp(argv[i],"-D",2)||!strncmp(argv[i],"-X",2)||!strncmp(argv[i],"--add-opens=",12)||!strncmp(argv[i],"--add-exports=",14)||!strncmp(argv[i],"--enable-native-access=",23))options[count++].optionString=argv[i];
        else if(argv[i][0]!='-'||!strcmp(argv[i],"-jar"))break;
    }
    JavaVMInitArgs init={0};init.version=JNI_VERSION_1_8;init.nOptions=count;init.options=options;
    JavaVM *vm=NULL;JNIEnv *env=NULL;
    if(create(&vm,(void **)&env,&init)!=JNI_OK){fprintf(stderr,"Cannot start Java VM\n");return 5;}
    jclass entry=(*env)->FindClass(env,"DevKitJavaEntry"),string=(*env)->FindClass(env,"java/lang/String");
    if(!entry||!string){(*env)->ExceptionDescribe(env);return 6;}
    const char *name=strrchr(argv[0],'/');name=name?name+1:argv[0];
    jobjectArray args=(*env)->NewObjectArray(env,argc,string,NULL);
    (*env)->SetObjectArrayElement(env,args,0,(*env)->NewStringUTF(env,name));
    for(int i=1;i<argc;i++)(*env)->SetObjectArrayElement(env,args,i,(*env)->NewStringUTF(env,argv[i]));
    jmethodID main=(*env)->GetStaticMethodID(env,entry,"main","([Ljava/lang/String;)V");
    if(main)(*env)->CallStaticVoidMethod(env,entry,main,args);
    int status=0;if((*env)->ExceptionCheck(env)){(*env)->ExceptionDescribe(env);(*env)->ExceptionClear(env);status=1;}
    (*vm)->DestroyJavaVM(vm);return status;
}
