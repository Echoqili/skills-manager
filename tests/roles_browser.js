'use strict';
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {execFileSync}=require('child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.join(__dirname,'..');
const adminHtml=execFileSync('python',['-c','from jinja2 import Template;from pathlib import Path;import sys;print(Template(Path(sys.argv[1]).read_text(encoding="utf-8")).render(proxy_auth=True))',path.join(root,'web/templates/admin_approvals.html')],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}});
const read=file=>fs.readFileSync(path.join(root,file),'utf8');
const defs=[{key:'skill_view',name:'查看与搜索 Skills',desc:'浏览技能'},{key:'skill_import',name:'导入 Skill',desc:'导入技能'}];
const baseUser={status:'approved',hide_unauthorized:false,must_change_password:false,created_at:'2026-10-13'};

async function main(){
 const browser=await chromium.launch({headless:true});
 let failed=0;
 async function test(name,url,run,force=false){
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();page.setDefaultTimeout(5000);
  const state={actor:{...baseUser,id:1,username:'superAdmin',is_admin:true,is_super_admin:true,permissions:['*'],must_change_password:force},
   member:{...baseUser,id:3,username:'member',is_admin:false,is_super_admin:false,permissions:['skill_view']},errors:[],posts:[],accounts:[]};
  state.accounts=[{...state.actor},{...baseUser,id:2,username:'manager',is_admin:true,is_super_admin:false,permissions:['skill_view']},{...state.member}];
  page.on('pageerror',e=>state.errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.route('**/*',async route=>{
   const request=route.request(),u=new URL(request.url()),p=u.pathname;
   if(p==='/super-admin')return route.fulfill({contentType:'text/html',body:read('web/templates/super_admin.html')});
   if(p==='/admin')return route.fulfill({contentType:'text/html',body:adminHtml});
   if(p==='/')return route.fulfill({contentType:'text/html',body:read('web/templates/index.html')});
   if(p==='/static/js/admin-session.js')return route.fulfill({contentType:'application/javascript',body:read('web/static/js/admin-session.js')});
   if(!p.startsWith('/api/'))return route.abort();
   let data={};
   if(request.method()==='POST'){
    const body=request.postDataJSON();state.posts.push({path:p,body});
    const user=state.accounts.find(a=>a.username===body.username);
    if(p.endsWith('/role')){user.is_admin=body.role==='admin';user.must_change_password=user.is_admin;}
    else if(p.endsWith('/status'))user.status=body.enabled?'approved':'disabled';
    else if(p.endsWith('/permissions')){user.permissions=body.permissions;user.hide_unauthorized=body.hide_unauthorized;}
    else if(p==='/api/auth/visibility'){state.member.hide_unauthorized=body.hide_unauthorized;}
    else if(p.endsWith('/visibility'))user.hide_unauthorized=body.hide_unauthorized;
    else if(p.endsWith('/change-password'))state.actor.must_change_password=false;
    data={success:true,hide_unauthorized:body.hide_unauthorized};
   }else if(p==='/api/auth/me')data={user:state.member};
   else if(p==='/api/admin/me'||p==='/api/super-admin/me')data={user:state.actor};
   else if(p==='/api/super-admin/users')data={users:state.accounts};
   else if(p==='/api/admin/users')data={users:state.accounts.filter(a=>!a.is_admin)};
   else if(p.endsWith('/permissions'))data={permissions:defs,all:'*'};
   else if(p.endsWith('/pending')||p.endsWith('/history'))data={users:[],logs:[]};
   else if(p==='/api/config')data={email_verify_required:false};
   else if(p==='/api/stats')data={total:1,categories:[]};
   else if(p==='/api/skills/all')data={total:1,results:[{name:'guide',id:'design/guide',namespace:'design',category:'design',description:'Guide'}]};
   else if(p==='/api/registry/index.json')data={skills:[{name:'guide',id:'design/guide',namespace:'design',version:'1',trust_score:80,quality_grade:'A',risk_level:'safe',download_url:'/api/registry/design/guide/download'}]};
   return route.fulfill({json:data});
  });
  try{await page.goto('http://roles.test'+url);await run(page,state);assert.deepEqual(state.errors,[]);console.log('[PASS] '+name);}
  catch(e){failed++;console.error('[FAIL] '+name+': '+e.stack);}
  finally{await context.close();}
 }
 await test('超级管理员独立管理管理员并支持空权限与隐藏', '/super-admin',async(page,state)=>{
  await page.locator('[data-action="permissions"][data-user="manager"]').waitFor();
  assert.equal(await page.locator('#permissionsMask').isVisible(),false);
  await page.locator('[data-action="permissions"][data-user="manager"]').click();
  await page.locator('#permissionOptions input[value="skill_view"]').uncheck();
  await page.locator('#hideNoPermission').check();await page.locator('#savePermissions').click();
  await page.locator('#permissionsMask').waitFor({state:'hidden'});
  assert.deepEqual(state.accounts.find(u=>u.username==='manager').permissions,[]);
  assert.equal(state.accounts.find(u=>u.username==='manager').hide_unauthorized,true);
  await page.locator('#promoteUser').selectOption('member');await page.locator('#promoteBtn').click();
  await page.locator('[data-action="demote"][data-user="member"]').waitFor();
  assert.equal(state.accounts.find(u=>u.username==='member').is_admin,true);
  await page.locator('[data-action="status"][data-user="manager"]').click();
  await page.waitForFunction(()=>document.getElementById('accounts').textContent.includes('已禁用'));
  await page.locator('[data-action="demote"][data-user="member"]').click();
  await page.locator('[data-action="demote"][data-user="member"]').waitFor({state:'detached'});
  assert.equal(state.accounts.find(u=>u.username==='member').is_admin,false);
 });
 await test('初始超级管理员必须改密码且不能提前加载管理数据','/super-admin',async(page,state)=>{
  await page.locator('#adminPasswordDialog').waitFor();
  assert.equal(await page.locator('[data-action]').count(),0);
  await page.locator('#apOld').fill('InitialRole#123456');await page.locator('#apNew').fill('UpdatedRole#987654');await page.locator('#apConfirm').fill('UpdatedRole#987654');
  await page.locator('#adminPasswordDialog [type="submit"]').click();
  await page.locator('[data-action="permissions"][data-user="manager"]').waitFor();
  assert.equal(state.actor.must_change_password,false);
 },true);
 await test('普通系统一键隐藏无权限功能并保存偏好','/',async(page,state)=>{
  await page.locator('#permissionVisibilityBtn').waitFor();
  const imports=page.locator('.sidebar .nav-tab[data-tab="import"]');
  await imports.waitFor();assert.ok(await imports.evaluate(el=>el.classList.contains('permission-denied')));
  await page.locator('#permissionVisibilityBtn').click();await imports.waitFor({state:'hidden'});
  await page.locator('#cartToggleBtn').waitFor({state:'hidden'});
  await page.evaluate(()=>toggleCartSidebar());
  assert.equal(await page.locator('#cartSidebar').evaluate(el=>el.classList.contains('show')),false);
  await page.locator('.sidebar .nav-tab[data-tab="registry"]').click();
  await page.locator('#registryList a[download]').waitFor({state:'attached'});
  await page.locator('#registryList a[download]').waitFor({state:'hidden'});
  assert.equal(state.member.hide_unauthorized,true);
  await page.locator('#permissionVisibilityBtn').click();await imports.waitFor({state:'visible'});
  assert.equal(state.member.hide_unauthorized,false);
 });
 await test('审批台权限弹窗支持隐藏选项和一键设置','/admin',async(page,state)=>{
  await page.locator('[data-tab="perms"]').click();await page.locator('[data-perm="member"]').waitFor();
  assert.equal(await page.locator('#permMask').isVisible(),false);
  await page.locator('[data-perm="member"]').click();await page.locator('#hideUnauthorized').check();
  await page.locator('#permSave').click();await page.locator('#permMask').waitFor({state:'hidden'});
  assert.equal(state.accounts.find(u=>u.username==='member').hide_unauthorized,true);
  await page.locator('[data-hide="member"]').click();
  await page.waitForFunction(()=>document.querySelector('[data-hide="member"]')?.textContent.includes('一键隐藏'));
  assert.equal(state.accounts.find(u=>u.username==='member').hide_unauthorized,false);
 });
 await browser.close();process.exitCode=failed?1:0;
}
main().catch(e=>{console.error(e);process.exitCode=1;});
