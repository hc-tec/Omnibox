from modelscope.hub.snapshot_download import snapshot_download
from sentence_transformers import SentenceTransformer

# ModelScope 上的模型 ID 可能不同，但 moka-ai/m3e-base 这个 ID 恰好它也支持
model_id = 'xrunda/m3e-base'
# model_id = 'damo/m3e-base' # 这个是达摩院在 modelscope 上的官方 ID，也可以用

# 1. 先用 modelscope 把模型下载到本地
# 它会自动使用国内镜像，速度很快
model_dir = snapshot_download(model_id)

# 2. model_dir 是下载后的本地文件夹路径，让 SentenceTransformer 从这里加载
model = SentenceTransformer(model_dir)

print("模型加载成功！")

#Our sentences we like to encode
sentences = [
    '* Moka 此文本嵌入模型由 MokaAI 训练并开源，训练脚本使用 uniem',
    '* Massive 此文本嵌入模型通过**千万级**的中文句对数据集进行训练',
    '* Mixed 此文本嵌入模型支持中英双语的同质文本相似度计算，异质文本检索等功能，未来还会支持代码检索，ALL in one'
]

#Sentences are encoded by calling model.encode()
embeddings = model.encode(sentences)

#Print the embeddings
for sentence, embedding in zip(sentences, embeddings):
    print("Sentence:", sentence)
    print("Embedding:", embedding)
    print("")
