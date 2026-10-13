const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const {buildSandbox,extractInlineScript}=require('./render_contract');
const root=path.join(__dirname,'..');
const sandbox=buildSandbox(),ctx=vm.createContext(sandbox);
vm.runInContext(extractInlineScript(fs.readFileSync(path.join(root,'web/templates/index.html'),'utf8')),ctx);
function element(tab){
 const classes=new Set();
 return {dataset:{tab},classList:{toggle(c,on){if(on)classes.add(c);else classes.delete(c);},contains(c){return classes.has(c);}},setAttribute(){},getAttribute(){return '';},classes};
}
const read=element('search'),imports=element('import'),settings=element('ai'),controls=[read,imports,settings];
sandbox.document.querySelectorAll=selector=>selector==='.nav-tab[data-tab]'||selector==='[data-permission]'?controls:[];
vm.runInContext("window.CURRENT_USER={id:1,is_admin:true,permissions:['skill_view'],hide_unauthorized:false};applyPermissionVisibility()",ctx);
assert.equal(vm.runInContext("canUsePermission('skill_import')",ctx),false);
assert.equal(imports.classes.has('permission-denied'),true);
assert.equal(imports.classes.has('permission-hidden'),false);
let payload;
sandbox.fetch=async (url,options)=>{assert.equal(url,'/api/auth/visibility');payload=JSON.parse(options.body);return {ok:true,json:async()=>({success:true,hide_unauthorized:true})};};
(async()=>{
 await vm.runInContext('togglePermissionVisibility()',ctx);
 assert.equal(payload.hide_unauthorized,true);
 assert.equal(imports.classes.has('permission-hidden'),true);
 assert.equal(settings.classes.has('permission-hidden'),true);
 assert.equal(read.classes.has('permission-hidden'),false);
 vm.runInContext("window.CURRENT_USER={is_super_admin:true,permissions:[],hide_unauthorized:true};applyPermissionVisibility()",ctx);
 assert.equal(imports.classes.has('permission-hidden'),false);
 console.log('PASS administrators obey assigned functional permissions');
 console.log('PASS one-click hiding persists and only removes unauthorized controls');
 console.log('PASS super administrator retains full access');
})().catch(e=>{console.error(e);process.exitCode=1;});
