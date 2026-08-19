using NUnit.Framework;
using UnityEngine;

namespace QIWEN.GameTemplates.Tests
{
    public sealed class GameTemplateEditModeTests
    {
        [Test, Category("模拟")]
        public void 模拟_层数与缺陷共同决定完成()
        {
            var demo = new GameObject().AddComponent<LayeringSimulationTemplate>();
            demo.Configure(2);
            Assert.That(demo.ApplyLayer(false), Is.True);
            Assert.That(demo.ApplyLayer(true), Is.True);
            Assert.That(demo.IsComplete, Is.False);
            Assert.That(demo.PolishDefect(), Is.True);
            Assert.That(demo.IsComplete, Is.True);
            Object.DestroyImmediate(demo.gameObject);
        }

        [Test, Category("时机")]
        public void 时机_容差内命中容差外失误()
        {
            var demo = new GameObject().AddComponent<RhythmTimingTemplate>();
            demo.Configure(1, 0.1f);
            Assert.That(demo.Strike(0.11f), Is.False);
            Assert.That(demo.Strike(-0.05f), Is.True);
            Assert.That(demo.IsComplete, Is.True);
            Object.DestroyImmediate(demo.gameObject);
        }

        [Test, Category("收集")]
        public void 收集_重复样本不重复计数()
        {
            var demo = new GameObject().AddComponent<CollectionTemplate>();
            demo.Configure(2);
            Assert.That(demo.Collect("漆液"), Is.True);
            Assert.That(demo.Collect("漆液"), Is.False);
            Assert.That(demo.Collect("木胎"), Is.True);
            Assert.That(demo.IsComplete, Is.True);
            Object.DestroyImmediate(demo.gameObject);
        }

        [Test, Category("谜题")]
        public void 谜题_错误步骤保留进度并记录失误()
        {
            var demo = new GameObject().AddComponent<SequencePuzzleTemplate>();
            demo.Configure(new[] { "清理", "底漆" });
            Assert.That(demo.SubmitStep("阴干"), Is.False);
            Assert.That(demo.CurrentStep, Is.Zero);
            Assert.That(demo.SubmitStep("清理"), Is.True);
            Assert.That(demo.SubmitStep("底漆"), Is.True);
            Assert.That(demo.IsComplete, Is.True);
            Object.DestroyImmediate(demo.gameObject);
        }

        [Test, Category("目标")]
        public void 目标_空刷和重复目标均不计分()
        {
            var demo = new GameObject().AddComponent<SimpleTargetTemplate>();
            demo.Configure(2);
            Assert.That(demo.AimAndHit("纹样一", false), Is.False);
            Assert.That(demo.AimAndHit("纹样一", true), Is.True);
            Assert.That(demo.AimAndHit("纹样一", true), Is.False);
            Assert.That(demo.AimAndHit("纹样二", true), Is.True);
            Assert.That(demo.IsComplete, Is.True);
            Object.DestroyImmediate(demo.gameObject);
        }
    }
}
