using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace QIWEN.GameTemplates.Tests
{
    public sealed class GameTemplatePlayModeTests
    {
        [UnityTest, Category("模拟")]
        public IEnumerator 模拟_跨帧保持层积状态() { var demo = new GameObject().AddComponent<LayeringSimulationTemplate>(); demo.Configure(1); demo.ApplyLayer(true); yield return null; Assert.That(demo.IsComplete, Is.True); Object.Destroy(demo.gameObject); }

        [UnityTest, Category("时机")]
        public IEnumerator 时机_跨帧保持命中状态() { var demo = new GameObject().AddComponent<RhythmTimingTemplate>(); demo.Configure(1, .1f); demo.Strike(0); yield return null; Assert.That(demo.IsComplete, Is.True); Object.Destroy(demo.gameObject); }

        [UnityTest, Category("收集")]
        public IEnumerator 收集_跨帧保持唯一物品() { var demo = new GameObject().AddComponent<CollectionTemplate>(); demo.Configure(1); demo.Collect("漆液"); yield return null; Assert.That(demo.IsComplete, Is.True); Object.Destroy(demo.gameObject); }

        [UnityTest, Category("谜题")]
        public IEnumerator 谜题_跨帧保持工序进度() { var demo = new GameObject().AddComponent<SequencePuzzleTemplate>(); demo.Configure(new[] { "阴干" }); demo.SubmitStep("阴干"); yield return null; Assert.That(demo.IsComplete, Is.True); Object.Destroy(demo.gameObject); }

        [UnityTest, Category("目标")]
        public IEnumerator 目标_跨帧保持落点状态() { var demo = new GameObject().AddComponent<SimpleTargetTemplate>(); demo.Configure(1); demo.AimAndHit("纹样", true); yield return null; Assert.That(demo.IsComplete, Is.True); Object.Destroy(demo.gameObject); }
    }
}
