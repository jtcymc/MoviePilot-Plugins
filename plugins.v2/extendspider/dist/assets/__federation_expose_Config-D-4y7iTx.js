import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,withKeys:_withKeys,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = { class: "plugin-config" };
const _hoisted_2 = { class: "d-flex align-center" };
const _hoisted_3 = { class: "d-flex justify-end mt-4" };

const {ref,reactive,onMounted,computed} = await importShared('vue');


// 接收初始配置和API对象

const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
  api: {
    // type: Object,
    default: () => {},
  },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;

// 表单状态
const form = ref(null);
const isFormValid = ref(true);
const error = ref('');
const saving = ref(false);

// 默认爬虫配置
const defaultSpiderConfigs = {
  "Bt1louSpider": {
    spider_name: 'Bt1louSpider',
    spider_enable: true,
    spider_proxy: false,
    pass_cloud_flare: true,
    proxy_type: 'playwright',
    spider_desc: 'BT之家1LOU站-回归初心，追求极简',
    spider_tags: ['电影', '电视剧', '动漫', '纪录片', '综艺'],
  },
  "BtBtlSpider": {
    spider_name: 'BtBtlSpider',
    spider_enable: true,
    spider_proxy: false,
    proxy_type: 'playwright',
    spider_desc: 'BT影视_4k高清电影BT下载_蓝光迅雷电影下载_最新电视剧下载',
  },
  "BtBuLuoSpider": {
    spider_name: 'BtBuLuoSpider',
    spider_enable: true,
    spider_proxy: false,
    proxy_type: 'playwright',
    spider_desc: 'BT部落天堂 - 注重体验与质量的影视资源下载网站',
  },
  "BtdxSpider": {
    spider_name: 'BtdxSpider',
    spider_enable: true,
    spider_proxy: false,
    proxy_type: 'playwright',
    spider_desc: '比特大雄_BT电影天堂_最新720P、1080P高清电影BT种子免注册下载网站',
  },
  "BtttSpider": {
    spider_name: 'BtttSpider',
    spider_enable: true,
    spider_proxy: false,
    proxy_type: 'playwright',
    spider_desc: 'BT天堂 - 2025最新高清电影1080P|2160P|4K资源免费下载',
  },
  "Dytt8899Spider": {
    spider_name: 'Dytt8899Spider',
    spider_enable: true,
    spider_proxy: false,
    proxy_type: 'playwright',
    spider_desc: '电影天堂_电影下载_高清首发',
  },
  "Bt0lSpider": {
    spider_name: 'Bt0lSpider',
    spider_enable: true,
    spider_proxy: false,
    proxy_type: 'playwright',
    spider_desc: '不太灵-影视管理系统',
  },
  "CiLiXiongSpider": {
    spider_name: 'CiLiXiongSpider',
    spider_enable: true,
    spider_proxy: false,
    pass_cloud_flare: true,
    proxy_type: 'playwright',
    spider_desc: '磁力熊，支持完结影视',
  },
  "GyingKSpider": {
    spider_name: 'GyingKSpider',
    spider_enable: true,
    spider_proxy: false,
    pass_cloud_flare: false,
    proxy_type: 'playwright',
    spider_desc: '观影 GYING',
    spider_username: '',
    spider_password: '',
  },
};

// 响应式数据
const config = reactive({
  enabled: false,
  cron: "0 0 */24 * *",
  onlyonce: false,
  spider_config: { ...defaultSpiderConfigs },
  tags: [],
});

// 计算属性：将spider_config转换为数组形式
ref(Object.values(config.spider_config));

// 配置JSON文本域数据
const spiderConfigJson = reactive({});
const spiderConfigErrors = reactive({});

// 标签管理
ref('');
const newTags = reactive({});

// 初始化配置
onMounted(() => {
  console.log(props.api);
  if (props.initialConfig) {
    Object.assign(config, props.initialConfig);
    if (props.initialConfig.spider_config) {
      config.spider_config = { ...defaultSpiderConfigs, ...props.initialConfig.spider_config };
    }
  }
  // 初始化JSON配置
  Object.keys(config.spider_config).forEach(spider_name => {
    spiderConfigJson[spider_name] = JSON.stringify(config.spider_config[spider_name], null, 2);
    newTags[spider_name] = '';
  });
});

// 自定义事件
const emit = __emit;

// 处理爬虫开关
async function handleSpiderToggle(spider_name) {
  try {
    const result = await props.api.post('plugin/ExtendSpider/toggle_spider', {
      spider_name
    });
    if (result.success) {
      error.value = null;
    } else {
      error.value = result.message;
    }
  } catch (err) {
    error.value = err.message || '操作失败';
  }
}

// 处理JSON配置变更
function handleConfigJsonChange(spider_name) {
  try {
    const newConfig = JSON.parse(spiderConfigJson[spider_name]);
    // 验证必要的字段
    if (!newConfig.spider_name || !newConfig.spider_desc) {
      throw new Error('配置缺少必要字段')
    }
    // 更新配置
    config.spider_config[spider_name] = newConfig;
    spiderConfigErrors[spider_name] = '';
  } catch (err) {
    spiderConfigErrors[spider_name] = 'JSON格式错误或缺少必要字段';
  }
}

// 处理重置单个爬虫配置
async function handleResetConfig(spider_name) {
  try {
    const result = await props.api.post('plugin/ExtendSpider/reset_config', {
      spider_name
    });
    if (result.success) {
      config.spider_config[spider_name] = { ...defaultSpiderConfigs[spider_name] };
      spiderConfigJson[spider_name] = JSON.stringify(defaultSpiderConfigs[spider_name], null, 2);
      error.value = null;
    } else {
      error.value = result.message;
    }
  } catch (err) {
    error.value = err.message || '重置失败';
  }
}

// 处理重置所有配置
async function handleResetAllConfig() {
  try {
    const result = await props.api.post('plugin/ExtendSpider/reset_all_config');
    if (result.success) {
      config.spider_config = { ...defaultSpiderConfigs };
      // 更新所有JSON配置
      Object.keys(defaultSpiderConfigs).forEach(spider_name => {
        spiderConfigJson[spider_name] = JSON.stringify(defaultSpiderConfigs[spider_name], null, 2);
      });
      error.value = null;
    } else {
      error.value = result.message;
    }
  } catch (err) {
    error.value = err.message || '重置失败';
  }
}

// 保存配置
async function saveConfig() {
  if (!isFormValid.value) {
    error.value = '请修正表单错误';
    return
  }

  saving.value = true;
  error.value = null;

  try {
    // 发送保存事件
    emit('save', { ...config });
  } catch (err) {
    console.error('保存配置失败:', err);
    error.value = err.message || '保存配置失败';
  } finally {
    saving.value = false;
  }
}

// 通知主应用切换到详情页面
function notifySwitch() {
  emit('switch');
}

// 通知主应用关闭当前页面
function notifyClose() {
  emit('close');
}

// 添加标签
async function addTag(spider_name) {
  if (!newTags[spider_name]) return
  
  try {
    await props.api.post('plugin/ExtendSpider/add_tag', {
      spider_name,
      tag: newTags[spider_name]
    });
    if (!config.spider_config[spider_name].spider_tags) {
      config.spider_config[spider_name].spider_tags = [];
    }
    config.spider_config[spider_name].spider_tags.push(newTags[spider_name]);
    newTags[spider_name] = '';
  } catch (err) {
    console.error('添加标签失败:', err);
    error.value = err.message || '添加标签失败';
  }
}

// 删除标签
async function removeTag(spider_name, tag) {
  try {
    await props.api.post('plugin/ExtendSpider/remove_tag', {
      spider_name,
      tag
    });
    const index = config.spider_config[spider_name].spider_tags.indexOf(tag);
    if (index > -1) {
      config.spider_config[spider_name].spider_tags.splice(index, 1);
    }
  } catch (err) {
    console.error('删除标签失败:', err);
    error.value = err.message || '删除标签失败';
  }
}

return (_ctx, _cache) => {
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_item = _resolveComponent("v-card-item");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_switch = _resolveComponent("v-switch");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_expansion_panel_title = _resolveComponent("v-expansion-panel-title");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_textarea = _resolveComponent("v-textarea");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_chip_group = _resolveComponent("v-chip-group");
  const _component_v_expansion_panel_text = _resolveComponent("v-expansion-panel-text");
  const _component_v_expansion_panel = _resolveComponent("v-expansion-panel");
  const _component_v_expansion_panels = _resolveComponent("v-expansion-panels");
  const _component_v_form = _resolveComponent("v-form");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_v_card, null, {
      default: _withCtx(() => [
        _createVNode(_component_v_card_item, null, {
          append: _withCtx(() => [
            _createVNode(_component_v_btn, {
              icon: "",
              color: "primary",
              variant: "text",
              onClick: notifyClose
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { left: "" }, {
                  default: _withCtx(() => _cache[4] || (_cache[4] = [
                    _createTextVNode("mdi-close")
                  ])),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, null, {
              default: _withCtx(() => _cache[3] || (_cache[3] = [
                _createTextVNode("爬虫配置")
              ])),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_card_text, { class: "overflow-y-auto" }, {
          default: _withCtx(() => [
            (error.value)
              ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 0,
                  type: "error",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(error.value), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            _createVNode(_component_v_form, {
              ref_key: "form",
              ref: form,
              modelValue: isFormValid.value,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((isFormValid).value = $event)),
              onSubmit: _withModifiers(saveConfig, ["prevent"])
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, { class: "mb-4" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_card_title, null, {
                      default: _withCtx(() => _cache[5] || (_cache[5] = [
                        _createTextVNode("基础设置")
                      ])),
                      _: 1
                    }),
                    _createVNode(_component_v_card_text, null, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_switch, {
                          modelValue: config.enabled,
                          "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((config.enabled) = $event)),
                          label: "启用插件",
                          color: "primary",
                          "hide-details": "",
                          class: "mb-4"
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_v_text_field, {
                          modelValue: config.cron,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.cron) = $event)),
                          label: "更新周期",
                          hint: "Cron表达式，例如：0 */6 * * *",
                          "persistent-hint": "",
                          variant: "outlined",
                          density: "comfortable"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _cache[12] || (_cache[12] = _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold mt-4 mb-2" }, "爬虫配置", -1)),
                _createVNode(_component_v_expansion_panels, { variant: "accordion" }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(config.spider_config, (spider, spider_name) => {
                      return (_openBlock(), _createBlock(_component_v_expansion_panel, { key: spider_name }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_expansion_panel_title, null, {
                            default: _withCtx(() => [
                              _createElementVNode("div", _hoisted_2, [
                                _createVNode(_component_v_icon, {
                                  color: spider.spider_enable ? 'success' : 'error',
                                  class: "mr-2"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(spider.spider_enable ? 'mdi-check-circle' : 'mdi-close-circle'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"]),
                                _createTextVNode(" " + _toDisplayString(spider.spider_name) + " - " + _toDisplayString(spider.spider_desc), 1)
                              ])
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(_component_v_expansion_panel_text, null, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_row, null, {
                                default: _withCtx(() => [
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_switch, {
                                        modelValue: spider.spider_enable,
                                        "onUpdate:modelValue": $event => ((spider.spider_enable) = $event),
                                        label: "启用爬虫",
                                        color: "primary",
                                        inset: "",
                                        onChange: $event => (handleSpiderToggle(spider_name))
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "onChange"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_switch, {
                                        modelValue: spider.spider_proxy,
                                        "onUpdate:modelValue": $event => ((spider.spider_proxy) = $event),
                                        label: "使用代理",
                                        color: "primary",
                                        inset: ""
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_switch, {
                                        modelValue: spider.pass_cloud_flare,
                                        "onUpdate:modelValue": $event => ((spider.pass_cloud_flare) = $event),
                                        label: "绕过CloudFlare",
                                        color: "primary",
                                        inset: ""
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    md: "6"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_select, {
                                        modelValue: spider.proxy_type,
                                        "onUpdate:modelValue": $event => ((spider.proxy_type) = $event),
                                        label: "代理类型",
                                        items: ['playwright', 'requests'],
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, { cols: "12" }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_textarea, {
                                        modelValue: spider.spider_desc,
                                        "onUpdate:modelValue": $event => ((spider.spider_desc) = $event),
                                        label: "爬虫描述",
                                        variant: "outlined",
                                        rows: "2",
                                        readonly: ""
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, { cols: "12" }, {
                                    default: _withCtx(() => [
                                      _cache[7] || (_cache[7] = _createElementVNode("div", { class: "text-subtitle-1 mb-2" }, "标签管理", -1)),
                                      _createVNode(_component_v_row, null, {
                                        default: _withCtx(() => [
                                          _createVNode(_component_v_col, {
                                            cols: "12",
                                            sm: "8"
                                          }, {
                                            default: _withCtx(() => [
                                              _createVNode(_component_v_text_field, {
                                                modelValue: newTags[spider_name],
                                                "onUpdate:modelValue": $event => ((newTags[spider_name]) = $event),
                                                label: "添加新标签",
                                                variant: "outlined",
                                                density: "comfortable",
                                                onKeyup: _withKeys($event => (addTag(spider_name)), ["enter"])
                                              }, null, 8, ["modelValue", "onUpdate:modelValue", "onKeyup"])
                                            ]),
                                            _: 2
                                          }, 1024),
                                          _createVNode(_component_v_col, {
                                            cols: "12",
                                            sm: "4",
                                            class: "d-flex align-center"
                                          }, {
                                            default: _withCtx(() => [
                                              _createVNode(_component_v_btn, {
                                                color: "primary",
                                                block: "",
                                                onClick: $event => (addTag(spider_name)),
                                                disabled: !newTags[spider_name]
                                              }, {
                                                default: _withCtx(() => _cache[6] || (_cache[6] = [
                                                  _createTextVNode(" 添加标签 ")
                                                ])),
                                                _: 2
                                              }, 1032, ["onClick", "disabled"])
                                            ]),
                                            _: 2
                                          }, 1024)
                                        ]),
                                        _: 2
                                      }, 1024),
                                      _createVNode(_component_v_chip_group, { class: "mt-4" }, {
                                        default: _withCtx(() => [
                                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(spider.spider_tags || [], (tag) => {
                                            return (_openBlock(), _createBlock(_component_v_chip, {
                                              key: tag,
                                              color: "primary",
                                              variant: "outlined",
                                              closable: "",
                                              "onClick:close": $event => (removeTag(spider_name, tag)),
                                              class: "ma-1"
                                            }, {
                                              default: _withCtx(() => [
                                                _createTextVNode(_toDisplayString(tag), 1)
                                              ]),
                                              _: 2
                                            }, 1032, ["onClick:close"]))
                                          }), 128))
                                        ]),
                                        _: 2
                                      }, 1024)
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, { cols: "12" }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_textarea, {
                                        modelValue: spiderConfigJson[spider_name],
                                        "onUpdate:modelValue": [$event => ((spiderConfigJson[spider_name]) = $event), $event => (handleConfigJsonChange(spider_name))],
                                        label: "爬虫配置（JSON格式）",
                                        variant: "outlined",
                                        rows: "6",
                                        "error-messages": spiderConfigErrors[spider_name]
                                      }, null, 8, ["modelValue", "onUpdate:modelValue", "error-messages"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_v_col, {
                                    cols: "12",
                                    class: "d-flex justify-end"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_btn, {
                                        color: "warning",
                                        variant: "outlined",
                                        class: "mr-2",
                                        onClick: $event => (handleResetConfig(spider_name))
                                      }, {
                                        default: _withCtx(() => _cache[8] || (_cache[8] = [
                                          _createTextVNode(" 重置配置 ")
                                        ])),
                                        _: 2
                                      }, 1032, ["onClick"])
                                    ]),
                                    _: 2
                                  }, 1024)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_3, [
                  _createVNode(_component_v_btn, {
                    color: "warning",
                    variant: "outlined",
                    class: "mr-2",
                    onClick: handleResetAllConfig
                  }, {
                    default: _withCtx(() => _cache[9] || (_cache[9] = [
                      _createTextVNode(" 重置所有配置 ")
                    ])),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    color: "info",
                    variant: "outlined",
                    class: "mr-2",
                    onClick: notifySwitch
                  }, {
                    default: _withCtx(() => _cache[10] || (_cache[10] = [
                      _createTextVNode(" 切换到详情 ")
                    ])),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    color: "primary",
                    disabled: !isFormValid.value,
                    onClick: saveConfig,
                    loading: saving.value
                  }, {
                    default: _withCtx(() => _cache[11] || (_cache[11] = [
                      _createTextVNode(" 保存配置 ")
                    ])),
                    _: 1
                  }, 8, ["disabled", "loading"])
                ])
              ]),
              _: 1
            }, 8, ["modelValue"])
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};
const ConfigComponent = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-b6a7e11e"]]);

export { ConfigComponent as default };
