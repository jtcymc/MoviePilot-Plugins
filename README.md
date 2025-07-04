# MoviePilot 插件
![Alt](https://repobeats.axiom.co/api/embed/9edb5f934bb2d49e463ce4b0962615656e8ea10b.svg "Repobeats analytics image")
> **免责声明**  
> 本项目及其插件仅供学习与交流使用，严禁用于任何商业或非法用途。请遵守当地法律法规，因使用本项目产生的任何后果由使用者自行承担。

## 特别注意事项
本项目的插件涉及更改源代码，请勿直接使用。适配官方版本的插件请使用 [MoviePilot-PluginsV2](https://github.com/jtcymc/MoviePilot-PluginsV2) 项目。

## 插件目录

### V2版本插件

#### Jackett Shaw
- 插件名称: Jackett Shaw
- 插件描述: 让内荐索引器支持检索Jackett站点资源
- 插件版本: 1.2
- 插件作者: shaw
- 作者主页: https://github.com/jtcymc
- 主要功能:
  - 支持配置Jackett服务器信息
  - 定时获取索引器列表
  - 支持搜索功能
  - 提供Web界面配置
  - 支持定时任务
  - 支持代理服务器配置
- 使用方法:
  1. 在配置页面填写:
     - Jackett服务器地址
     - API Key
     - 密码(可选)
     - 更新周期
  2. 点击"立即运行一次"可以立即获取索引器列表
  3. 插件会自动定时更新索引器列表
  4. 可以在详情页面查看已获取的索引器列表
- 注意事项:
  - 需要先在Jackett中添加indexer
  - 才能正常测试通过和使用
  - 建议配置代理服务器以提高访问稳定性

#### Prowlarr Shaw
- 插件名称: Prowlarr Shaw
- 插件描述: 让内荐索引器支持检索Prowlarr站点资源
- 插件版本: 1.2
- 插件作者: shaw
- 作者主页: https://github.com/jtcymc
- 主要功能:
  - 支持配置Prowlarr服务器信息
  - 定时获取索引器列表
  - 支持搜索功能
  - 提供Web界面配置
  - 支持定时任务
  - 支持代理服务器配置
- 使用方法:
  1. 在配置页面填写:
     - Prowlarr服务器地址
     - API Key
     - 更新周期
  2. 点击"立即运行一次"可以立即获取索引器列表
  3. 插件会自动定时更新索引器列表
  4. 可以在详情页面查看已获取的索引器列表
- 注意事项:
  - 需要先在Prowlarr中添加搜刮器
  - 同时勾选所有搜刮器后搜索一次
  - 才能正常测试通过和使用
  - 建议配置代理服务器以提高访问稳定性

#### ExtendSpider
- 插件名称: ExtendSpider
- 插件描述: 以插件的方式获取索引器信息，支持更多的站点
- 插件版本: 1.2
- 插件作者: shaw
- 作者主页: https://github.com/jtcymc
- 主要功能:
  - 支持多个BT站点资源检索
  - 支持站点资源搜索
  - 支持资源信息解析
  - 支持种子下载链接获取
  - 支持站点状态监控
  - 支持代理服务器配置
- 使用方法:
  1. 在配置页面启用需要的站点
  2. 配置代理服务器（可选）
  3. 设置更新周期
  4. 点击"立即运行一次"可以立即获取站点资源
- 注意事项:
  - 确保网络环境能够正常访问这些站点
  - 部分站点可能需要配置代理才能访问
  - 建议定期检查站点可用性
  - 建议配置代理服务器以提高访问稳定性

#### JackettExtend
- 插件名称: JackettExtend
- 插件描述: 扩展检索以支持Jackett站点资源
- 插件版本: 1.0
- 插件作者: jtcymc
- 作者主页: https://github.com/jtcymc
- 主要功能:
  - 支持配置Jackett服务器信息
  - 支持搜索功能
  - 提供Web界面配置
  - 支持代理服务器配置
- 使用方法:
  1. 在配置页面填写:
     - Jackett服务器地址
     - API Key
     - 密码(可选)
  2. 配置代理服务器（可选）
  3. 启用插件即可使用
- 注意事项:
  - 需要先在Jackett中添加indexer
  - 建议配置代理服务器以提高访问稳定性

### ExtendSpider 插件支持的 BT 站点

每个站点插件都支持：
- 站点资源搜索
- 资源信息解析
- 种子下载链接获取
- 站点状态监控

使用这些插件时，建议：
1. 确保网络环境能够正常访问这些站点
2. 部分站点可能需要配置代理才能访问
3. 建议定期检查站点可用性


![](https://raw.githubusercontent.com/jtcymc/MoviePilot-Plugins/refs/heads/main/docs/imgs/img.png)
![](https://raw.githubusercontent.com/jtcymc/MoviePilot-Plugins/refs/heads/main/docs/imgs/img_1.png)