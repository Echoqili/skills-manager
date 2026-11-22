const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const {buildSandbox,extractInlineScript}=require('./render_contract');
const root=path.join(__dirname,'..');
const sandbox=buildSandbox(),ctx=vm.createContext(sandbox);
vm.runInContext(extractInlineScript(fs.readFileSync(path.join(root,'web/templates/index.html'),'utf8')),ctx);
function element(tab){
 const classes=new Set();
 return {dataset:{tab},classList:{toggle(c,on){if(on)classes.add(c);else classes.delete(c);},contains(c){return classes.has(c);}},setAttribute(){},getAttribute(){return '';},classes};
}
const read=element('search'),imports=element('import'),settings=element('ai');
const updateTab=element('update'),releaseTab=element('releases');
const aiTab=settings; // 智能设置 nav-tab 与 settings 是同一元素
const syncLink=element('local-sync');syncLink.dataset.permission='local_sync';
// 真实 DOM 中 search/import/ai/update/releases 都是 nav-tab，applyPermissionVisibility 会按 tab 写入 permission
const allNavTabs=[read,imports,settings,updateTab,releaseTab];
sandbox.document.querySelectorAll=selector=>{
 if(selector==='.nav-tab[data-tab]')return allNavTabs;
 if(selector==='[data-permission]')return [...allNavTabs,syncLink];
 return [];
};
vm.runInContext("window.CURRENT_USER={id:1,is_admin:true,permissions:['skill_view']};applyPermissionVisibility()",ctx);
assert.equal(vm.runInContext("canUsePermission('skill_import')",ctx),false);
assert.equal(imports.classes.has('permission-denied'),true);
assert.equal(imports.classes.has('permission-hidden'),false);
// 三项系统级功能映射到独立权限点，基础权限用户不可用
assert.equal(vm.runInContext("canUsePermission('auto_update')",ctx),false);
assert.equal(vm.runInContext("canUsePermission('release_view')",ctx),false);
assert.equal(vm.runInContext("canUsePermission('ai_settings')",ctx),false);
assert.equal(updateTab.classes.has('permission-denied'),true);
assert.equal(releaseTab.classes.has('permission-denied'),true);
assert.equal(aiTab.classes.has('permission-denied'),true);
assert.equal(syncLink.classes.has('permission-denied'),true);
assert.equal(vm.runInContext('SECTION_PERMISSIONS.update',ctx),'auto_update');
assert.equal(vm.runInContext('SECTION_PERMISSIONS.releases',ctx),'release_view');
assert.equal(vm.runInContext('SECTION_PERMISSIONS.ai',ctx),'ai_settings');
assert.equal(vm.runInContext('SECTION_PERMISSIONS.discover',ctx),'discover');
// 未开启隐藏时，即使被收紧了业务权限，入口仍显示（只是灰掉）
assert.equal(imports.classes.has('permission-hidden'),false);
// 普通用户开启隐藏后：无权限功能（含四项系统级）隐藏，有权限功能保留
vm.runInContext("window.CURRENT_USER={id:2,is_admin:false,is_super_admin:false,permissions:['skill_view'],hide_unauthorized:true};applyPermissionVisibility()",ctx);
assert.equal(imports.classes.has('permission-hidden'),true);
assert.equal(settings.classes.has('permission-hidden'),true);
assert.equal(updateTab.classes.has('permission-hidden'),true);
assert.equal(releaseTab.classes.has('permission-hidden'),true);
assert.equal(syncLink.classes.has('permission-hidden'),true);
assert.equal(read.classes.has('permission-hidden'),false);
// 关闭隐藏后入口恢复显示
vm.runInContext("window.CURRENT_USER={id:2,is_admin:false,is_super_admin:false,permissions:['skill_view'],hide_unauthorized:false};applyPermissionVisibility()",ctx);
assert.equal(imports.classes.has('permission-hidden'),false);
// 顶栏按钮自助切换：调 /api/auth/visibility，回写字段并刷新隐藏状态
let payload;
sandbox.fetch=async (url,options)=>{assert.equal(url,'/api/auth/visibility');payload=JSON.parse(options.body);return {ok:true,json:async()=>({success:true,hide_unauthorized:payload.hide_unauthorized})};};
(async()=>{
 await vm.runInContext('togglePermissionVisibility()',ctx);
 assert.equal(payload.hide_unauthorized,true);
 assert.equal(imports.classes.has('permission-hidden'),true);
 assert.equal(settings.classes.has('permission-hidden'),true);
 assert.equal(read.classes.has('permission-hidden'),false);
 vm.runInContext("window.CURRENT_USER={is_super_admin:true,permissions:[],hide_unauthorized:true};applyPermissionVisibility()",ctx);
 assert.equal(imports.classes.has('permission-hidden'),false);
 console.log('PASS administrators obey assigned functional permissions');
 console.log('PASS hide toggle persists and only removes unauthorized controls');
 console.log('PASS super administrator retains full access');
})().catch(e=>{console.error(e);process.exitCode=1;});
