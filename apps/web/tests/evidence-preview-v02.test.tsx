import {fireEvent,render,screen,within} from "@testing-library/react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {EvidencePreview,OCRPage} from "@/components/evidence-preview";

const pages:OCRPage[]=[
  {id:"p1",page_number:1,width:1000,height:1000,regions:[{id:"r1",raw_text:"二月工资6000元",bbox_x:100,bbox_y:200,bbox_width:300,bbox_height:50,confidence:.96}]},
  {id:"p2",page_number:2,width:1000,height:1000,regions:[{id:"r2",raw_text:"三月仅支付1000元",bbox_x:50,bbox_y:100,bbox_width:400,bbox_height:60,confidence:.88}]},
];
const image={kind:"image" as const,content_url:"/api/evidence/e1/content"};

describe("EvidencePreview v0.2",()=>{
  afterEach(()=>vi.restoreAllMocks());
  it("点击原图 OCR 框会同步选中文本",()=>{render(<EvidencePreview preview={image} pages={pages.slice(0,1)} segments={[]}/>);fireEvent.click(screen.getByTestId("region-r1"));expect(within(screen.getByLabelText("OCR 文本定位轨")).getByRole("button",{name:/二月工资/})).toHaveAttribute("aria-pressed","true")});
  it("点击 OCR 文本会同步选中原图框",()=>{render(<EvidencePreview preview={image} pages={pages.slice(0,1)} segments={[]}/>);fireEvent.click(within(screen.getByLabelText("OCR 文本定位轨")).getByRole("button",{name:/二月工资/}));expect(screen.getByTestId("region-r1")).toHaveAttribute("aria-pressed","true")});
  it("多页证据可以切换到下一页",()=>{render(<EvidencePreview preview={image} pages={pages} segments={[]}/>);fireEvent.click(screen.getByRole("button",{name:"下一页"}));expect(screen.getByText("第 2 / 2 页")).toBeInTheDocument();expect(screen.getByText("三月仅支付1000元")).toBeInTheDocument()});
  it("切换页码会清除上一页区域选择",()=>{render(<EvidencePreview preview={image} pages={pages} segments={[]}/>);fireEvent.click(screen.getByTestId("region-r1"));fireEvent.click(screen.getByRole("button",{name:"下一页"}));expect(screen.getByTestId("region-r2")).toHaveAttribute("data-active","false")});
  it("第一页禁用上一页且末页禁用下一页",()=>{render(<EvidencePreview preview={image} pages={pages} segments={[]}/>);expect(screen.getByRole("button",{name:"上一页"})).toBeDisabled();fireEvent.click(screen.getByRole("button",{name:"下一页"}));expect(screen.getByRole("button",{name:"下一页"})).toBeDisabled()});
  it("DOCX 派生 HTML 以文档预览呈现",()=>{render(<EvidencePreview preview={{kind:"document",content_url:"/x",html:"<h1>工资记录</h1><p>已脱敏内容</p>"}} pages={[]} segments={[]}/>);expect(screen.getByLabelText("文档派生预览")).toHaveTextContent("工资记录");expect(screen.getByText("已脱敏内容")).toBeInTheDocument()});
  it("CSV/XLSX 的多个工作表和单元格可读",()=>{render(<EvidencePreview preview={{kind:"table",content_url:"/x",sheets:[{name:"工资表",rows:[["期间","应发"],["2026-02","6000"]]},{name:"代付",rows:[["付款人","金额"]]}]}} pages={[]} segments={[]}/>);expect(screen.getByRole("heading",{name:"工资表"})).toBeInTheDocument();expect(screen.getByText("2026-02")).toBeInTheDocument();expect(screen.getByRole("heading",{name:"代付"})).toBeInTheDocument()});
  it("表格截断时明确提示展示上限",()=>{render(<EvidencePreview preview={{kind:"table",content_url:"/x",sheets:[],truncated:true}} pages={[]} segments={[]}/>);expect(screen.getByText("仅显示前 200 行、50 列。")).toBeInTheDocument()});
  it("TXT 证据使用保留换行的文本预览",()=>{render(<EvidencePreview preview={{kind:"text",content_url:"/x",text:"第一行\n第二行"}} pages={[]} segments={[]}/>);expect(screen.getByText(/第一行\s+第二行/)).toBeInTheDocument()});
  it("音频片段点击后跳转时间并标记当前片段",()=>{vi.spyOn(HTMLMediaElement.prototype,"play").mockResolvedValue();render(<EvidencePreview preview={{kind:"audio",content_url:"/api/evidence/a1/content"}} pages={[]} segments={[{id:"s1",speaker_id:"说话人A",start_time:"12.5",end_time:"15.2",text:"工资晚几天发"}]}/>);const segment=screen.getByRole("button",{name:/工资晚几天发/});fireEvent.click(segment);expect(document.querySelector("audio")?.currentTime).toBe(12.5);expect(segment).toHaveAttribute("aria-pressed","true")});
  it("音频片段显示说话人与精确时间范围",()=>{render(<EvidencePreview preview={{kind:"audio",content_url:"/x.wav"}} pages={[]} segments={[{id:"s1",speaker_id:"说话人B",start_time:1,end_time:2.25,text:"收到"}]}/>);expect(screen.getByText("说话人B")).toBeInTheDocument();expect(screen.getByText("1.00–2.25")).toBeInTheDocument()});
});
