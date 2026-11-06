import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {defaultSettings,normalizeProviders,normalizeSettings,SettingsPanel} from "@/components/settings-panel";

function response(data:unknown,status=200){return new Response(JSON.stringify({data}),{status,headers:{"content-type":"application/json"}})}
function renderPanel(){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><SettingsPanel/></QueryClientProvider>)}
describe("SettingsPanel v0.2",()=>{
  afterEach(()=>vi.restoreAllMocks());
  it("缺少服务端字段时保留隐私优先默认值",()=>{expect(normalizeSettings({llm_provider:"qwen"})).toEqual({...defaultSettings,llm_provider:"qwen"})});
  it("把后端 offline_mode 映射为页面运行模式",()=>{expect(normalizeSettings({offline_mode:false}).mode).toBe("online")});
  it("兼容 Provider 数组响应",()=>{expect(normalizeProviders([{name:"ollama",status:"available"}])).toHaveLength(1)});
  it("兼容按能力分组的 Provider 响应",()=>{expect(normalizeProviders({llm:{provider:"ollama",available:true,model:"qwen3:8b"}})).toEqual([{name:"ollama",kind:"llm",status:"available",model:"qwen3:8b",detail:undefined}])});
  it("明确显示 5090 路演版并允许离线配置 Ollama",async()=>{
    vi.spyOn(globalThis,"fetch").mockImplementation(async input=>{
      const url=String(input);
      if(url.endsWith("/api/system/app-profile"))return response({edition:"roadshow",configuration_mode:"environment",locked:true,model_root:{path:"E:\\models",source:"environment",registration_allowed:false}});
      if(url.endsWith("/api/system/settings"))return response({...defaultSettings,llm_provider:"ollama"});
      if(url.endsWith("/api/system/llm-config"))return response({provider:"ollama",base_url:"",model:"",api_key_configured:false,storage:"windows-dpapi",storage_available:true,returned:false});
      return response([]);
    });
    renderPanel();
    expect(await screen.findByRole("heading",{name:"5090 本地路演版"})).toBeInTheDocument();
    expect(await screen.findByDisplayValue("http://127.0.0.1:11434/v1")).toBeInTheDocument();
    expect(screen.queryByLabelText("API 密钥")).not.toBeInTheDocument();
    expect(screen.getByRole("button",{name:"保存能力设置"})).toBeDisabled();
  });
  it("载入服务端设置和真实 Provider 状态",async()=>{vi.spyOn(globalThis,"fetch").mockImplementation(async input=>String(input).endsWith("/api/system/settings")?response({...defaultSettings,llm_provider:"deepseek"}):response([{name:"rapidocr",kind:"ocr",status:"available"}]));renderPanel();expect(await screen.findByDisplayValue("deepseek")).toBeInTheDocument();expect(await screen.findByText("rapidocr")).toBeInTheDocument();expect(screen.getByText("available")).toBeInTheDocument()});
  it("在线模式未经同意不能保存",async()=>{vi.spyOn(globalThis,"fetch").mockImplementation(async input=>String(input).endsWith("/api/system/settings")?response({...defaultSettings,llm_provider:"qwen-local"}):response([]));renderPanel();await screen.findByDisplayValue("qwen-local");fireEvent.click(screen.getByRole("button",{name:/在线增强/}));expect(screen.getByRole("button",{name:"保存能力设置"})).toBeDisabled()});
  it("在线同意后可将 PATCH 设置发送至后端",async()=>{const fetch=vi.spyOn(globalThis,"fetch").mockImplementation(async(input,init)=>{if(init?.method==="PATCH")return response({saved:true});return String(input).endsWith("/api/system/settings")?response({...defaultSettings,llm_provider:"qwen-local"}):response([])});renderPanel();await screen.findByDisplayValue("qwen-local");fireEvent.click(screen.getByRole("button",{name:/在线增强/}));fireEvent.click(screen.getByText("我已了解在线发送范围"));fireEvent.click(screen.getByRole("button",{name:"保存能力设置"}));await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/system/settings"),expect.objectContaining({method:"PATCH",body:expect.stringContaining('"offline_mode":false')}))) });
  it("展示无需下载的基础模式和可由用户主动安装的本地能力包",async()=>{
    vi.spyOn(globalThis,"fetch").mockImplementation(async input=>{
      const url=String(input);
      if(url.endsWith("/api/system/settings"))return response(defaultSettings);
      if(url.endsWith("/api/system/model-manager"))return response({
        onboarding_required:true,
        automatic_downloads:false,
        basic_mode:{ready:true,provider:"rapidocr",description:"基础案件整理、文书和 CPU OCR 无需下载大型模型。"},
        model_root:"D:\\LaborCaseAgent\\models",
        runtime_root:"D:\\LaborCaseAgent\\runtimes",
        system:{os:"Windows",architecture:"AMD64",disk_free_bytes:30_000_000_000,nvidia_gpu:null},
        packs:[{id:"bge-m3",name:"本地语义检索",capability:"embedding",description:"按语义查找已确认事实",repo_id:"BAAI/bge-m3",revision:"abc",license:"MIT",model_bytes:4_000_000_000,runtime_bytes:5_000_000_000,runtime:"embedding",python_version:"3.12",hardware:"cpu_or_nvidia_gpu",minimum_vram_gb:4,source_url:"https://huggingface.co/BAAI/bge-m3",license_url:"https://huggingface.co/BAAI/bge-m3/blob/main/LICENSE",dependency_summary:["Python 3.12"],remote_code:false,recommended:true,requires_consent:true,installed:false,status:"model_missing",model_present:false,runtime_present:false,model_path:"D:\\models\\bge-m3",runtime_path:"D:\\runtimes\\python.exe"}]
      });
      return response([]);
    });
    renderPanel();
    expect(await screen.findByText("基础模式已可用")).toBeInTheDocument();
    expect(screen.getByRole("heading",{name:"本地语义检索"})).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"安装本地语义检索"})).toBeInTheDocument();
    expect(screen.getByText(/不会自动下载/)).toBeInTheDocument();
  });
  it("在线模式允许用户填写并测试自己的 API 配置",async()=>{
    const fetch=vi.spyOn(globalThis,"fetch").mockImplementation(async(input,init)=>{
      const url=String(input);
      if(url.endsWith("/api/system/settings"))return response({...defaultSettings,llm_provider:"openai-compatible"});
      if(url.endsWith("/api/system/llm-config")&&init?.method==="PATCH")return response({api_key_configured:true});
      if(url.endsWith("/api/system/llm-config/test")&&init?.method==="POST")return response({ok:true,provider:"openai-compatible",base_url:"https://api.example.test/v1",model:"example-model",latency_ms:18,message:"连接成功"});
      if(url.endsWith("/api/system/llm-config"))return response({provider:"openai-compatible",base_url:"https://api.example.test/v1",model:"example-model",api_key_configured:false,storage:"windows-dpapi",storage_available:true,returned:false});
      return response([]);
    });
    renderPanel();
    await waitFor(()=>expect(screen.getByLabelText("语言模型")).toHaveValue("openai-compatible"));
    fireEvent.click(screen.getByRole("button",{name:/在线增强/}));
    expect(await screen.findByDisplayValue("https://api.example.test/v1")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("API 密钥"),{target:{value:"sk-user-secret"}});
    fireEvent.click(screen.getByRole("button",{name:"测试连接"}));
    expect(await screen.findByText(/连接成功/)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/system/llm-config/test"),expect.objectContaining({method:"POST",body:expect.stringContaining('"api_key":"sk-user-secret"')}));
  });
});
