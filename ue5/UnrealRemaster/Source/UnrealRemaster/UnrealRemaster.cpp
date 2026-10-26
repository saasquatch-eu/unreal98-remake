#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogUnrealRemaster, Log, All);

class FUnrealRemasterModule final : public FDefaultGameModuleImpl
{
public:
    virtual void StartupModule() override
    {
        UE_LOG(LogUnrealRemaster, Display, TEXT("UnrealRemaster primary C++ module loaded."));
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FUnrealRemasterModule, UnrealRemaster, "UnrealRemaster");
