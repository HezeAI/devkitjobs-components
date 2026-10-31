"use strict";
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const cp = require("node:child_process");
const upstream = path.join(__dirname, "openscad.js");
function invoke(args, capture = false) {
  const result = cp.spawnSync(process.execPath, [upstream, ...args], {
    stdio: capture ? "pipe" : "inherit", encoding: capture ? "utf8" : undefined,
    timeout: 60000, maxBuffer: 1024 * 1024,
  });
  if (result.error) throw result.error;
  const informational = args.length === 1 && ["--version", "--help", "--info"].includes(args[0]);
  // Upstream 2026.10.29 WASM returns 7 for informational commands; exports must return 0.
  if (result.status !== 0 && !(informational && result.status === 7)) {
    if (capture) process.stderr.write((result.stdout || "") + (result.stderr || ""));
    throw new Error("OpenSCAD failed: " + result.status + " / " + result.signal);
  }
  return result;
}
function measure(data) {
  const n = data.readUInt32LE(80);
  if (data.length !== 84+50*n) throw new Error("Invalid binary STL");
  let lo = [Infinity,Infinity,Infinity], hi = [-Infinity,-Infinity,-Infinity], vol = 0;const edges=new Map();
  for (let t=0; t<n; t++) {
    let v=[];
    for(let i=0; i<3; i++) {
      const p=[];
      for(let a=0; a<3; a++) {
        const x=data.readFloatLE(84+50*t+12+12*i+4*a);
        if(!Number.isFinite(x)) throw new Error("Invalid coordinate");
        lo[a]=Math.min(lo[a],x); hi[a]=Math.max(hi[a],x); p.push(x);
      }
      v.push(p);
    }
    for(let i=0;i<3;i++){const a=v[i].join(","),b=v[(i+1)%3].join(",");if(a===b)throw new Error("Degenerate STL edge");const k=a<b?a+"|"+b:b+"|"+a,prev=edges.get(k)||[0,0];edges.set(k,[prev[0]+1,prev[1]+(a<b?1:-1)]);}
    const [a,b,c]=v;
    vol+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6;
  }
  if(!n||vol<=0||[...edges.values()].some(([count,direction])=>count!==2||direction!==0))throw new Error("Non-closed, misoriented or empty mesh");
  return {triangles:n, dimensions:hi.map((x,i)=>x-lo[i]), volume:vol,closed:true,unit:"mm (fixture convention; STL is unitless)"};
}
if(process.argv[2] === "--devkit-self-test") {
  if(process.arch !== "arm64") throw new Error("ARM64 Node.js required");
  const version=invoke(["--version"],true);
  const versionText=(version.stdout+version.stderr).trim();
  if(!versionText.includes("OpenSCAD")) throw new Error("Missing OpenSCAD version");
  console.log(versionText);
  console.log("Upstream version-query exit:", version.status);
  console.log("Runtime:", process.version, process.arch, process.platform);
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),"openscad-functional-"));
  try {
    const cases=[
      ["cube", "cube([1,2,3]);", [1,2,3], 6],
      ["boolean", "difference(){cube([8,6,4]);translate([2,2,1])cube([4,2,4]);}", [8,6,4], 168],
      ["extrude", "linear_extrude(height=4,scale=0.5)square([4,4]);", [4,4,4], 112/3]
    ];
    for(const [name,scad,dims,vol] of cases) {
      const input=path.join(dir,name+".scad"), output=path.join(dir,name+".stl");
      fs.writeFileSync(input,scad);
      invoke(["--export-format=binstl","-o",output,input],true);
      const actual=measure(fs.readFileSync(output));
      if(actual.dimensions.some((x,i)=>Math.abs(x-dims[i])>1e-5)||Math.abs(actual.volume-vol)>0.001)
        throw new Error("Geometry mismatch: "+JSON.stringify(actual));
      console.log(name+": "+JSON.stringify(actual));
    }
    console.log("OpenSCAD functional checks passed");
  } finally { fs.rmSync(dir,{recursive:true,force:true}); }
} else {
  invoke(process.argv.slice(2));
}
