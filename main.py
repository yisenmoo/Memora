from core.orchestrator import orchestrate
from llm.router import list_models
import sys

def select_model():
    print("\n📋 可用模型列表：")
    models = list_models()
    for idx, m in enumerate(models):
        print(f"  [{idx+1}] {m['id']:<15} : {m['description']}")
    print()

    default_model = "qwen3-30b"
    while True:
        model_input = input(f"使用哪个模型？(默认 {default_model})：\n").strip()
        
        model = model_input or default_model
        
        # 简单的数字选择支持
        if model.isdigit():
            idx = int(model) - 1
            if 0 <= idx < len(models):
                return models[idx]["id"]
        
        # Check if valid ID
        if any(m['id'] == model for m in models):
            return model
            
        print(f"❌ 未知模型: {model}，请重新选择")

if __name__ == "__main__":
    try:
        current_model = select_model()
        print(f"\n🚀 已选模型: {current_model}")
        print("💡 输入 'exit', 'quit' 或 Ctrl+C 退出程序")
        print("💡 输入 'switch' 切换模型")
        print("-" * 30)

        while True:
            try:
                question = input("\n👤 你想让 Agent 做什么？\n> ").strip()
                if not question:
                    continue
                
                if question.lower() in ["exit", "quit"]:
                    print("👋 Bye!")
                    break
                
                if question.lower() == "switch":
                    current_model = select_model()
                    print(f"\n🚀 已切换模型: {current_model}")
                    continue

                print(f"\n🤖 Agent ({current_model}) 正在执行...")
                # 核心修改：调用 orchestrate 而不是 plan
                result = orchestrate(question, model=current_model)
                print(f"\n🏁 最终结果:\n{result}")
                
            except KeyboardInterrupt:
                print("\n\n🛑 用户中断")
                break
            except Exception as e:
                print(f"\n❌ 执行出错: {e}")
                
    except KeyboardInterrupt:
        print("\n👋 Bye!")
