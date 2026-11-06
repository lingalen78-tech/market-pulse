const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

test('market tabs support click, arrows, Home and End with one visible panel', () => {
  const panels = [{hidden:false}, {hidden:false}, {hidden:false}];
  const tabs = panels.map((_, i) => ({
    attrs: {'aria-controls': String(i)}, handlers: {},
    setAttribute(k,v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; },
    addEventListener(k,fn) { this.handlers[k] = fn; }, focus() { this.focused = true; }
  }));
  vm.runInNewContext(fs.readFileSync(__dirname+'/market-charts.js','utf8'), {
    document: {querySelectorAll: () => [{querySelectorAll: () => tabs}], getElementById: id => panels[Number(id)]}
  });
  function selected(index) {
    assert.deepEqual(panels.map(p=>p.hidden), panels.map((_,i)=>i!==index));
    assert.deepEqual(tabs.map(t=>t.attrs['aria-selected']), tabs.map((_,i)=>String(i===index)));
    assert.deepEqual(tabs.map(t=>t.tabIndex), tabs.map((_,i)=>i===index?0:-1));
  }
  selected(0);
  tabs[2].handlers.click(); selected(2);
  let prevented = 0;
  const key = (index, name) => tabs[index].handlers.keydown({key:name,preventDefault(){prevented++;}});
  key(2,'ArrowRight'); selected(0);
  key(0,'ArrowLeft'); selected(2);
  key(2,'Home'); selected(0);
  key(0,'End'); selected(2);
  assert.equal(prevented,4);
  assert.equal(tabs[2].focused,true);
});
