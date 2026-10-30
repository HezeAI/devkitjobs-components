import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.util.*;
import java.util.jar.*;
import javax.tools.ToolProvider;

/** Headless JVM entry point; no dependency on the installed Termux prefix. */
public final class DevKitJavaEntry {
    public static void main(String[] original)throws Throwable {
        String tool=original[0];List<String> args=new ArrayList<>(Arrays.asList(original).subList(1,original.length));
        if(tool.equals("javac")){System.exit(ToolProvider.getSystemJavaCompiler().run(null,System.out,System.err,args.toArray(new String[0])));return;}
        if(tool.equals("jar")||tool.equals("javap")){
            java.util.spi.ToolProvider provider=java.util.spi.ToolProvider.findFirst(tool).orElseThrow(()->new IOException("JDK tool is unavailable"));
            System.exit(provider.run(System.out,System.err,args.toArray(new String[0])));return;
        }
        if(tool.equals("keytool"))args.add(0,"sun.security.tools.keytool.Main");
        if(tool.equals("d8")||tool.equals("apksigner")){
            args.add(0,tool.equals("d8")?"com.android.tools.r8.D8":"com.android.apksigner.ApkSignerTool");
            args.add(0,System.getenv("ANDROID_HOME")+"/build-tools/36.0.0/lib/"+(tool.equals("d8")?"d8.jar":"apksigner.jar"));args.add(0,"-cp");
        }
        if(tool.equals("gradle")){
            args.add(0,"org.gradle.launcher.GradleMain");
            args.add(0,System.getenv("GRADLE_HOME")+"/lib/gradle-gradle-cli-main-9.5.0.jar");args.add(0,"-cp");
        }
        String classPath=".",main=null;boolean jar=false;int position=0;
        for(;position<args.size();position++){
            String value=args.get(position);
            if(value.equals("--version")||value.equals("-version")){
                System.out.println(System.getProperty("java.runtime.name")+" "+System.getProperty("java.runtime.version"));
                System.out.println(System.getProperty("java.vm.name")+" · "+System.getProperty("os.arch"));return;
            }
            if(value.equals("-cp")||value.equals("-classpath")||value.equals("--class-path")){classPath=args.get(++position);continue;}
            if(value.equals("-jar")){jar=true;main=args.get(++position);position++;break;}
            if(value.startsWith("-"))continue;
            main=value;position++;break;
        }
        if(main==null)throw new IOException("Specify a main class or -jar");
        List<URL> urls=new ArrayList<>();
        if(jar){
            File archive=new File(main);urls.add(archive.toURI().toURL());
            try(JarFile file=new JarFile(archive)){main=file.getManifest().getMainAttributes().getValue("Main-Class");}
        }else for(String path:classPath.split(File.pathSeparator)){
            if(path.endsWith("/*")){File[] files=new File(path.substring(0,path.length()-2)).listFiles((directory,name)->name.endsWith(".jar"));if(files!=null)for(File file:files)urls.add(file.toURI().toURL());}
            else urls.add(new File(path).toURI().toURL());
        }
        try(URLClassLoader loader=new URLClassLoader(urls.toArray(new URL[0]),ClassLoader.getSystemClassLoader())){
            Thread.currentThread().setContextClassLoader(loader);
            try{Class.forName(main,true,loader).getMethod("main",String[].class).invoke(null,(Object)args.subList(position,args.size()).toArray(new String[0]));}
            catch(InvocationTargetException error){throw error.getCause();}
        }
    }
}
