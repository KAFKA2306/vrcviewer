# VRChatギャラリー

## 概要
このプロジェクトは、VRChatのアバターとワールドを閲覧できるWebギャラリーです。CSVファイルからデータを読み込み、視覚的に美しいインターフェースで表示します。

[https://kafka2306.github.io/vrcviewer/
](https://kafka2306.github.io/vrcviewer/)

## 特徴
- アバターとワールドを切り替えられるタブインターフェース
- 検索機能（名前やクリエイター名で検索可能）
- カテゴリーフィルター機能
- 画像をクリックするとVRChatの公式ページに直接アクセス可能

## 使い方
1. `index.html`をブラウザで開くだけで利用できます
2. 上部のタブでアバターとワールドを切り替えられます
3. 検索ボックスで名前やクリエイター名による検索が可能です
4. フィルターボタンでカテゴリー別に表示できます

## データの追加方法
新しいワールドを追加したい場合は、以下の形式でCSVファイルを作成してください：

```
ID,Name,Author ID,Author Name,Thumbnail
wrld_a50146fe-4730-4ea2-a4e2-1870751e232b,謎解きワールド Fake,usr_d816b4d3-d092-46b5-963d-df30862d6901,いぬんちゅ,https://api.vrchat.cloud/api/1/image/file_f5a3e796-8534-468e-921a-7865686c0750/6/256
```

ファイル名を`worlds_カテゴリー名.csv`の形式で保存すると、自動的にそのカテゴリー名がフィルターに追加されます。例えば、`worlds_event.csv`や`worlds_game.csv`などです。

## 必要なファイル
- `sample_avatars.csv` - アバターデータ
- `worlds_*.csv` - ワールドデータ（*はカテゴリー名）

ファイルを追加したら、スクリプトを再実行して`index.html`を更新してください。
